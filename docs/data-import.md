# Importing the legacy literature dump

This runbook covers the one-time import of the connectmv.com / Mercurial-era literature catalogue into the revived site. It assumes the legacy `Literature-full-backup--YYYY-MM-DD-HH-MM-SS.tar.bz2` produced by the old host's nightly backup script (the one that ran `python3 manage.py dumpdata --all --format json --indent 2`).

## What's in the tarball

The legacy backup script bundles two things into one tarball:

```
Literature-full-backup--YYYY-MM-DD-HH-MM-SS.tar.bz2
└── staging-YYYY-MM-DD-HH-MM-SS/
    ├── Literature--DjangoDump--YYYY-MM-DD-HH-MM-SS.json   ← what we want
    └── Django/                                             ← legacy code, ignore
```

The dumpdata JSON is what `manage.py import_legacy_dump` consumes. The `Django/` snapshot of the old codebase isn't needed for the import.

## Step 1 — extract the tarball

On any machine (your laptop is fine; doesn't need to be the prod host):

```bash
tar -xjf Literature-full-backup--YYYY-MM-DD-HH-MM-SS.tar.bz2
DUMP=$(find staging-* -name 'Literature--DjangoDump--*.json' -print -quit)
echo "Dump file: $DUMP"
ls -lh "$DUMP"
```

`$DUMP` should be a few hundred KB to a few MB depending on how many `Item` rows live in the legacy DB.

## Step 2 — dry-run the import

The command's `--dry-run` flag parses the dump, runs the same logic the real import would, then **rolls back the transaction** so the database is untouched. It prints a summary of how many rows of each type would land. Run it first to confirm the dump shape matches the importer's expectations.

> **`--file` is interpreted inside the `web` container.** The container only sees three host paths bind-mounted in (per `docker-compose.prod.yml`'s `volumes:` block): `.env`, `data/media/`, and `data/static/`. Anything else on the host is invisible. The cleanest way to feed in the dump is `docker cp` into the container's `/tmp/`, which gives a one-off path that disappears on container restart (no leftover dump sitting around in a bind mount).

On Hetzner:

```bash
ssh deploy@hetzner-host
cd /home/deploy/literature/repo

# Make sure the prod compose is up; web should be (healthy)
docker compose -f docker-compose.prod.yml ps

# Copy the dump into the running web container's /tmp/
docker cp path/to/legacy.json literature-app:/tmp/

# Dry-run with the in-container path
docker compose -f docker-compose.prod.yml exec web \
    python manage.py import_legacy_dump --file /tmp/legacy.json --dry-run
```

Or natively (uv) on a dev box, where `/tmp/legacy.json` is just the host path:

```bash
uv run python manage.py import_legacy_dump --file path/to/legacy.json --dry-run
```

You should see something like:

```
Would import:
  items.author: 204
  items.authorgroup: 442
  items.book: 10
  items.conferenceproceeding: 1
  items.journal: 37
  items.journalpub: 147
  items.publisher: 6
  items.school: 1
  items.thesis: 19
  m2m: items.item.tags: 528
  m2m: items.thesis.supervisors: 25
  pagehit.pagehit: 86248
  tagging.tag: 128
```

(That's the actual row inventory of the 2018-09-11 backup of `literature.connectmv.com`, used for the smoke run.)

If a count looks zero where you expected rows, or the command errors on parsing, stop and reconcile against the dump shape (`jq '.[].model' legacy.json | sort -u`) before doing the real import.

## Step 3 — run the import for real

**Recommended order**: import to the staging hostname (`test.literature.learnche.org`) first, sanity-check, then to prod. Both hostnames share the same `docker-compose.prod.yml` and the same Postgres container, so this is mostly about cautious sequencing rather than literal separate environments.

If you're importing to a brand-new (empty) production DB, you can run on `literature.learnche.org` directly. The dump file should already be in the container's `/tmp/` from Step 2; if you're starting fresh, `docker cp` it in again:

```bash
cd /home/deploy/literature/repo

# Skip if the dump is still in /tmp/ from the dry-run; otherwise:
docker cp path/to/legacy.json literature-app:/tmp/

# Run the import (no `--dry-run` this time)
docker compose -f docker-compose.prod.yml exec web \
    python manage.py import_legacy_dump --file /tmp/legacy.json
```

Watch the summary it prints; row counts should match the dry-run.

## Step 4 — verify

```bash
# Front page should show some "Recently added" titles after a refresh:
curl -fsS https://literature.learnche.org/ | grep -A1 'Recently added'

# Search should hit the seeded corpus:
curl -fsS 'https://literature.learnche.org/search?q=fourier'

# Tag cloud:
curl -fsS https://literature.learnche.org/item/show/all-tags/
```

In the admin (`/admin/`), spot-check 5 random `Item`s: title, authors, tags, full citation should all be populated. If `Item.pdf_file` is set, the file path should be `literature/pdf/<slug[0]>/<slug>.pdf` (no `media/` prefix — the import strips it). The PDF bytes themselves are **not** copied by this command; you'd ship `data/media/literature/pdf/` separately.

## What the import does (and doesn't)

**Handles automatically:**

- Multi-table inheritance: `Item` parent + `JournalPub` / `Book` / `ConferenceProceeding` / `Thesis` subclass records get merged so Django's auto-Item-row machinery doesn't double-write.
- M2M: `Item.tags`, `Book.editors`, `ConferenceProceeding.editors`, `Thesis.supervisors`.
- The `AuthorGroup` through-table linking `Item.authors`.
- Stripping the legacy `media/` prefix from `Item.pdf_file` paths (Phase-1 gotcha — new `upload_to` writes `literature/pdf/...`, no `media/`).
- Silently ignoring fields dropped in later phases:
  - `Item.private_pdf`, `Item.can_show_pdf` (Phase 5)
  - `PageHit.ua_string`, `PageHit.ip_address` (Phase 4)
- Dropping `auth.*`, `contenttypes.*`, `sessions.*`, `admin.logentry` records on the floor — the new install has its own.
- **Idempotent re-runs**: legacy primary keys are preserved (so existing links into specific items keep working). `update_or_create(pk=…)` updates rows in place rather than creating duplicates.

**Doesn't handle (do separately):**

- **The actual PDF byte payload.** The legacy filesystem layout is `<legacy MEDIA_ROOT>/pdf/<slug[0]>/<slug>.pdf` (no `literature/` subdir), but the in-DB `Item.pdf_file` values point at `literature/pdf/<slug[0]>/<slug>.pdf`. Bridge with a one-level rsync remap — the trailing slash on the source means "copy contents", so `pdf/a/<file>.pdf` from the legacy host lands at `literature/pdf/a/<file>.pdf` on Hetzner where the in-DB rows expect it:

  ```bash
  ssh deploy@<hetzner-host>
  mkdir -p /home/deploy/literature/repo/data/media/literature/pdf

  # Dry-run first
  rsync -avzn --stats --human-readable \
      <legacy-user>@<legacy-host>:/path/to/legacy/media/pdf/ \
      /home/deploy/literature/repo/data/media/literature/pdf/

  # Real run
  rsync -avz --stats --human-readable \
      <legacy-user>@<legacy-host>:/path/to/legacy/media/pdf/ \
      /home/deploy/literature/repo/data/media/literature/pdf/
  ```

  Verify by sampling 5 random in-DB paths and confirming each resolves to a file:

  ```bash
  cd /home/deploy/literature/repo
  docker compose -f docker-compose.prod.yml exec -T db sh -c \
    'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
     "SELECT pdf_file FROM items_item WHERE pdf_file <> '\'''\'' ORDER BY random() LIMIT 5;"' \
  | while read p; do
      [ -z "$p" ] && continue
      echo -n "$p ... "
      [ -f "/home/deploy/literature/repo/data/media/$p" ] && echo OK || echo MISSING
    done
  ```
- A pre-existing PageHit table on the new install. If you've been running the new site and accumulated hits, the import's `update_or_create(pk=...)` could conflict with new PageHit rows that share a legacy `pk`. In practice this is unlikely (the new install starts at `pk=1` and the legacy table has thousands of rows), but if you want to be paranoid, `psql -c "TRUNCATE pagehit_pagehit;"` before importing.
- Schema migrations for new constraints introduced post-Phase-1. The dump's field shapes have to be compatible with the current model definitions; if a field type narrowed (e.g. `max_length` shrank), some rows might fail.

## Troubleshooting

**`CommandError: Could not parse <path> as JSON`** — the file you pointed at isn't valid JSON. If you accidentally fed it the `.tar.bz2` instead of the extracted JSON, `tar -xjf` it first.

**`CommandError: Expected a JSON array`** — the dump came from a non-`dumpdata` source. The importer expects Django dumpdata format: a top-level JSON array of `{"model": ..., "pk": ..., "fields": ...}` records.

**`UNIQUE constraint failed`** — there's already a row with that legacy `pk` *and different content*. This shouldn't happen with `update_or_create`, but if you've manually crafted Items in the admin with low IDs that collide with the legacy data's, drop them first.

**Subclass record without parent** — `[skip] items.journalpub pk=N: no matching items.item record`. Means the dump is incomplete (the parent Item row is missing). Run `dumpdata` on the legacy DB again, making sure to include `items` (the dump should always pair every subclass row with its `items.item` parent).
