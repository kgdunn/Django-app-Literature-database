# Deploying `literature.learnche.org` to Hetzner

This runbook covers the **one-time host bootstrap** plus the auto-deploy wiring. After it's done, every push to `main` runs `.github/workflows/ci.yml`; **on successful CI completion**, `.github/workflows/deploy.yml` chains via `workflow_run` and SSHes to Hetzner via a forced-command key, running `bin/deploy-impl.sh` (which itself runs `docker compose -f docker-compose.prod.yml up -d --build` + a `/healthz` sanity curl). A failing CI run does not deploy. Manual `workflow_dispatch` (rollback / forced redeploy) bypasses the CI gate.

Production target:

| | |
| --- | --- |
| Hostname | `literature.learnche.org` (proxied through Cloudflare) |
| Staging hostname | `test.literature.learnche.org` (Cloudflare DNS-only) |
| VPS | The same Hetzner box that runs `openmv.net` |
| Code path | `/home/deploy/literature/repo/` |
| Web port (loopback) | `127.0.0.1:8002` |
| Postgres port (loopback) | `127.0.0.1:5435` |
| Reverse proxy | host-installed Caddy (shared with openmv) |
| TLS | Cloudflare Origin Cert at `/etc/caddy/origin-certs/literature.learnche.org/` |

## Prerequisites on the host

This assumes the host already has:

- Docker Engine + Docker Compose v2.
- Caddy v2 installed at the OS level (it serves openmv too).
- A `deploy` Linux user with passwordless `docker` group membership.

If any of those is missing, set them up first; they're orthogonal to literature.

## 1. Clone the repo and create the data dirs

As `deploy@` on Hetzner:

```bash
sudo mkdir -p /home/deploy/literature/{repo,backups,bin}
sudo chown -R deploy:deploy /home/deploy/literature

sudo -u deploy git clone https://github.com/kgdunn/Django-app-Literature-database.git \
    /home/deploy/literature/repo

sudo -u deploy mkdir -p /home/deploy/literature/repo/data/{media,static,public}
```

The three `data/*` dirs are bind-mounted into the `web` container by `docker-compose.prod.yml`:

| Host path | Container path | Purpose |
| --- | --- | --- |
| `data/media/` | `/app/media` | PDFs uploaded by the admin (admin-only — never exposed publicly; Phase 5 rule). Backed up to S3 in Phase 11. |
| `data/static/` | `/app/static` | `collectstatic` output. Regenerated on every container start. **Not** backed up. |
| `data/public/` | (served by Caddy) | Hand-curated public files (`robots.txt`, `favicon.ico`). |

## 2. Write `.env` with real values

```bash
sudo -u deploy cp /home/deploy/literature/repo/.env.example /home/deploy/literature/repo/.env
sudo -u deploy "$EDITOR" /home/deploy/literature/repo/.env
```

Fill in the file. The keys that **must** change from the example defaults:

```bash
# Generate locally with `python -c "import secrets; print(secrets.token_urlsafe(50))"`
SECRET_KEY=<a long random string>

# Strong production password (NOT 'literature' — that's the dev default).
POSTGRES_PASSWORD=<a strong random password>

# (Optional) override defaults if needed:
# ALLOWED_HOSTS=.literature.learnche.org,127.0.0.1
```

Notes:

- **No `sudo -u postgres psql` setup needed.** The Postgres user / database are created by the `db` service container on first boot (`postgres:16-alpine` reads `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` from the env at `initdb` time). The host doesn't need a Postgres install at all.
- `SQL_HOST` and `SQL_PORT` in `.env` are overridden inside `docker-compose.prod.yml` to `db` / `5432` (the in-compose-network address of the `db` service), so the values you put in `.env` for those keys are ignored in production. Keep the example values; they don't affect the prod stack.

## 3. (Optional, but recommended) Pin the `python:3.11-slim` digest

`Dockerfile` ships `FROM python:3.11-slim` without a digest pin. Pin it once on the prod box so a future Docker Hub repoint can't change the build silently:

```bash
docker pull python:3.11-slim
docker images --digests | grep '^python.*3.11-slim'
# Copy the sha256:... value from the DIGEST column.
```

Then edit `Dockerfile` (both stages) and replace `FROM python:3.11-slim` with `FROM python:3.11-slim@sha256:<digest>`. Commit the change to a feature branch, open a PR, let CI run; merge.

Dependabot's `docker` ecosystem (`.github/dependabot.yml`) will then keep that pin current.

## 4. First container boot

```bash
cd /home/deploy/literature/repo
sudo -u deploy docker compose -f docker-compose.prod.yml up -d --build
```

What happens:

1. `db` (postgres:16-alpine) starts. `initdb` creates the `literature` user and database from the `POSTGRES_*` env vars.
2. `db` becomes healthy via `pg_isready`.
3. `web` starts. Its compose `command:` runs `python manage.py migrate --noinput` (creates all tables, installs `pg_trgm` via the `items/0004_pg_trgm` migration), then `collectstatic --noinput` (writes into `/app/static`, i.e. `data/static/` on the host), then `gunicorn literature.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile - --error-logfile -`.

Sanity-check:

```bash
docker compose -f docker-compose.prod.yml ps
# web should be up; the Dockerfile HEALTHCHECK will flip it to (healthy)
# within ~30 s of gunicorn binding to 8000.

curl -fsS http://127.0.0.1:8002/healthz
# → ok
```

If `web` exits, inspect the logs:

```bash
docker compose -f docker-compose.prod.yml logs --tail=200 web
```

Common first-boot issues:
- **`SECRET_KEY must be set`** — `.env` is empty or missing the key. Fix it and `docker compose up -d`.
- **`POSTGRES_DB must be set ...`** — the `web` service depends on the same env vars at import time (`literature/settings/prod.py` asserts they're set). Fill in `.env`.

## 5. Cloudflare DNS

In the `learnche.org` Cloudflare zone:

| Type | Name | Value | Proxy status |
| --- | --- | --- | --- |
| `A` | `literature` | `<Hetzner v4 IP>` | **Proxied** (orange) |
| `AAAA` | `literature` | `<Hetzner v6 IP>` | **Proxied** (orange) |
| `A` | `test.literature` | `<Hetzner v4 IP>` | **DNS only** (grey) |
| `AAAA` | `test.literature` | `<Hetzner v6 IP>` | **DNS only** (grey) |

The `test.literature` records must stay DNS-only so Caddy's HTTP/TLS-ALPN challenge for the staging hostname can reach the box directly. The prod `literature` records are proxied for Cloudflare's edge cache + the Cloudflare-managed public TLS cert.

## 6. Cloudflare Origin Certificate

In the Cloudflare dashboard, **SSL/TLS → Origin Server → Create Certificate**:

- Hostnames: `literature.learnche.org`, `*.literature.learnche.org`
- Validity: 15 years (Cloudflare default)
- Format: PEM

Save the certificate as:

```
/etc/caddy/origin-certs/literature.learnche.org/cert.pem
/etc/caddy/origin-certs/literature.learnche.org/key.pem
```

Permissions:

```bash
sudo chown -R caddy:caddy /etc/caddy/origin-certs/literature.learnche.org
sudo chmod 600 /etc/caddy/origin-certs/literature.learnche.org/key.pem
sudo chmod 644 /etc/caddy/origin-certs/literature.learnche.org/cert.pem
```

Cloudflare's TLS mode for the zone should be **Full (strict)** so the edge re-encrypts to origin and validates the origin cert.

## 7. Caddy server block

Append the following to `/etc/caddy/Caddyfile` (alongside the existing openmv block):

```caddy
literature.learnche.org {
    tls /etc/caddy/origin-certs/literature.learnche.org/cert.pem \
        /etc/caddy/origin-certs/literature.learnche.org/key.pem

    encode zstd gzip

    # Static + media + public assets are served directly off disk for
    # speed; the gunicorn worker never sees these requests.
    handle_path /static/* {
        root * /home/deploy/literature/repo/data/static
        file_server
    }

    # Phase 5 / copyright: PDFs are admin-only. Block direct access to
    # /media/literature/pdf/* even though the bytes live on disk under
    # data/media. (data/media/ also stores future non-PDF assets, so we
    # don't want a blanket /media block.)
    @pdfs path /media/literature/pdf/*
    respond @pdfs 404

    handle_path /media/* {
        root * /home/deploy/literature/repo/data/media
        file_server
    }

    handle_path /public/* {
        root * /home/deploy/literature/repo/data/public
        file_server
    }

    # Everything else goes to gunicorn.
    reverse_proxy 127.0.0.1:8002 {
        header_up X-Forwarded-Proto https
        header_up X-Forwarded-For {remote_host}
    }

    log {
        output file /var/log/caddy/literature.log {
            roll_size 50mb
            roll_keep 10
        }
    }
}

# Staging — Caddy-managed Let's Encrypt cert (DNS-only at Cloudflare so
# the HTTP/TLS-ALPN challenge can reach origin).
test.literature.learnche.org {
    encode zstd gzip
    reverse_proxy 127.0.0.1:8002 {
        header_up X-Forwarded-Proto https
        header_up X-Forwarded-For {remote_host}
    }
}
```

Validate and reload:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Smoke-test:

```bash
curl -fsS https://literature.learnche.org/healthz
# → ok
```

## 8. SSH deploy key (forced command)

The `Deploy to Hetzner` workflow needs an SSH key that's locked to running only `bin/deploy.sh`.

### a. Generate the key locally

```bash
ssh-keygen -t ed25519 -N '' -f literature-deploy
# Produces literature-deploy (private) and literature-deploy.pub (public).
```

### b. Install the public half on Hetzner

As `deploy@` on the host, append to `~/.ssh/authorized_keys`:

```
command="/home/deploy/literature/bin/deploy.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 AAAAC3...<contents of literature-deploy.pub>...
```

The `command="…"` clause is the security mechanism: SSH ignores whatever the client tries to run and forces this script.

### c. Write the host-side wrapper

The wrapper lives **outside** the repo (so a malicious in-repo edit can't change what the forced command runs). Create `/home/deploy/literature/bin/deploy.sh` as `deploy@`:

```bash
#!/bin/bash
# Forced command for the literature-deploy SSH key. Fast-forwards the
# repo to origin/main and exec's the in-tree deploy script.
set -euo pipefail
REPO=/home/deploy/literature/repo
cd "$REPO"
git fetch --quiet origin
git reset --hard origin/main
exec "$REPO/bin/deploy-impl.sh"
```

```bash
sudo chmod 700 /home/deploy/literature/bin/deploy.sh
sudo chown deploy:deploy /home/deploy/literature/bin/deploy.sh
```

### d. Add the key to GitHub repo secrets

In the repo's **Settings → Secrets and variables → Actions**, add:

| Name | Value |
| --- | --- |
| `HETZNER_SSH_KEY` | the **private** half (`literature-deploy`, full file contents incl. headers) |
| `HETZNER_HOST` | the host's DNS name or IP, e.g. `your-hetzner-box.example.com` |
| `HETZNER_USER` | `deploy` |

Then delete the local `literature-deploy` private key file.

### e. Smoke-test the deploy

Push any trivial change to `main` (or use the GitHub Actions UI's `workflow_dispatch` button on `Deploy to Hetzner`) and watch the run. It should:

1. Open SSH
2. Hit the forced command, which fast-forwards the repo
3. Exec `bin/deploy-impl.sh`
4. Run `docker compose -f docker-compose.prod.yml up -d --build`
5. Curl `127.0.0.1:8002/healthz` ten times until it gets a 200
6. Exit 0

If step 5 times out, the workflow fails red and the last 40 lines of `web` container logs print into the Action output. To re-run the same diagnostic by hand from the host:

```bash
cd /home/deploy/literature/repo
docker compose -f docker-compose.prod.yml logs --tail=40 web
```

(Both the `-f docker-compose.prod.yml` flag and the `cd` matter — a bare `docker compose logs` from anywhere else on the host produces `no configuration file provided: not found`. The compose-project-name pin in `docker-compose.prod.yml` doesn't help compose discover the file; it only avoids stack-name collisions once compose has loaded the file.)

## 9. Manual deploys (rollback / hotfix)

Auto-deploy fires on every push to `main`. To roll back manually, SSH to Hetzner with a normal (non-forced-command) key and:

```bash
cd /home/deploy/literature/repo
git fetch
git reset --hard <prior commit SHA on main>
docker compose -f docker-compose.prod.yml up -d --build
```

Or to redeploy the current `main` HEAD without pushing anything:

```bash
ssh -i literature-deploy deploy@<host>
# (or trigger workflow_dispatch in the GitHub Actions UI)
```

## Compose project name and on-disk volumes

Both `docker-compose.yml` and `docker-compose.prod.yml` pin a top-level `name: literature` directive. **Don't remove it.** It's load-bearing for two distinct reasons:

1. **Teardown isolation.** Without it, Compose defaults the project name to the basename of the directory you invoke from — `repo`. The openmv stack at `/home/deploy/openmv/repo/` would also default to `repo`, and `docker compose -f docker-compose.prod.yml down` from either repo would tear out the *other* stack's containers too (literally observed on 2026-05-09 — `openmv-app` and `openmv-postgres` disappeared during a literature redeploy).

2. **Volume naming.** Compose names every named volume `<project>_<volume>` on disk. The pin means our Postgres data lives in **`literature_literature_postgres_data`**. The double `literature_` is intentional: the first comes from `name: literature`, the second from the volume key in `docker-compose.prod.yml`. Renaming the project also renames the volume — Compose creates a fresh, empty volume under the new name and the old data sits orphaned under the old name. The site would come back up with no data.

### Migration playbook (only if the project name ever changes)

If the project name ever changes (e.g. unpinning `name:` and going back to the directory-basename default, or moving the checkout to a differently-named directory), the old data sits in `<old_project>_literature_postgres_data` and the new compose will mount a freshly-empty `<new_project>_literature_postgres_data`. Migrate **before** bringing the new stack up — once the new compose boots it'll create the empty destination volume itself, and the safety of the cp step depends on the destination not pre-existing:

```bash
# 1. Verify the old volume exists and has data.
docker volume inspect <old_project>_literature_postgres_data
docker run --rm -v <old_project>_literature_postgres_data:/data alpine ls /data | head

# 2. Stop & remove the old containers — NOT with -v / --volumes
#    (that flag would destroy the volume too).
docker stop literature-app literature-postgres 2>/dev/null
docker rm   literature-app literature-postgres 2>/dev/null

# 3. Create the destination volume and copy the data across.
docker volume create <new_project>_literature_postgres_data
docker run --rm \
    -v <old_project>_literature_postgres_data:/from:ro \
    -v <new_project>_literature_postgres_data:/to \
    alpine sh -c 'cp -a /from/. /to/ && echo OK'

# 4. Sanity-check the destination.
docker run --rm -v <new_project>_literature_postgres_data:/data alpine ls /data | head

# 5. Bring up the new stack and verify.
cd /home/deploy/literature/repo
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec -T db \
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\dt' | head
curl -fsS http://127.0.0.1:8002/healthz

# 6. Only after verifying the site loads with the right row counts,
#    free the old volume:
# docker volume rm <old_project>_literature_postgres_data
```

This is the same playbook run against the openmv stack on 2026-05-09, when its project name was pinned: old volume `repo_openmv_postgres_data` → new volume `openmv_openmv_postgres_data`. (No literature data needed migrating because the legacy dump hadn't been imported into prod yet — but the same shape applies if it ever comes up.)

The `data/media/`, `data/static/`, and `data/public/` host directories are **bind mounts**, not named volumes. They're addressed by host path, so they survive a project rename untouched. Only the named Postgres volume is project-scoped.

## What's not in this runbook

- Off-host backups to S3 — **Phase 11**. `bin/backup-literature.sh` + a cron entry.
- Restore drill — Phase 11.
- Host-level fail2ban / Cloudflare WAF tuning — out of scope; orthogonal to literature.
