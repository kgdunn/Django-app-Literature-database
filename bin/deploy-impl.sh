#!/bin/bash
# Production deploy implementation for literature.learnche.org on Hetzner.
#
# Invoked by the wrapper at /home/deploy/literature/bin/deploy.sh (the
# wrapper lives outside the repo so a malicious in-repo edit can't change
# its contents). The wrapper fast-forwards origin/main into
# /home/deploy/literature/repo and then exec's THIS file from the
# freshly-pulled tree, so the deploy steps themselves remain reviewable
# in PRs.
#
# Run via the wrapper, not directly. The wrapper is the entry point
# baked into the SSH deploy key's authorized_keys forced-command (see
# docs/deploy.md).

set -euo pipefail

cd "$(dirname "$0")/.."

echo "[deploy-impl] $(date -u +%FT%TZ) starting; HEAD=$(git rev-parse --short HEAD)"

docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps

# Give the web container a few seconds to run migrate + collectstatic and
# bind to 8000 inside the container, then sanity-check it's responding.
# /healthz doesn't hit the DB, so this only fails if gunicorn itself is
# wedged (the db service has its own pg_isready healthcheck).
for _ in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sSf -o /dev/null --max-time 5 http://127.0.0.1:8002/healthz; then
        echo "[deploy-impl] web responding on 127.0.0.1:8002/healthz"
        echo "[deploy-impl] $(date -u +%FT%TZ) done"
        exit 0
    fi
    sleep 2
done

echo "[deploy-impl] web did not respond on 127.0.0.1:8002/healthz within 20s"
docker compose -f docker-compose.prod.yml logs --tail=40 web
exit 1
