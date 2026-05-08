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

Locally (Docker dev compose):

```bash
docker compose exec web python manage.py import_legacy_dump \
    --file /app/path/to/legacy.json --dry-run
```

Or natively (uv):

```bash
uv run python manage.py import_legacy_dump --file path/to/legacy.json --dry-run
```

You should see something like:

```
Would import:
  items.author: 87
  items.book: 6
  items.conferenceproceeding: 4
  items.journal: 14
  items.journalpub: 122
  items.publisher: 9
  items.school: 7
  items.thesis: 11
  items.authorgroup: 280
  m2m: items.book.editors: 3
  m2m: items.item.tags: 195
  m2m: items.thesis.supervisors: 14
  pagehit.pagehit: 38214
  tagging.tag: 33
```

If a count looks zero where you expected rows, or the command errors on parsing, stop and reconcile against the dump shape (`jq '.[].model' legacy.json | sort -u`) before doing the real import.

## Step 3 — run the import for real

**Recommended order**: import to the staging hostname (`test.literature.learnche.org`) first, sanity-check, then to prod. Both hostnames share the same `docker-compose.prod.yml` and the same Postgres container, so this is mostly about cautious sequencing rather than literal separate environments.

If you're importing to a brand-new (empty) production DB, you can run on `literature.learnche.org` directly:

```bash
ssh deploy@hetzner-host
cd /home/deploy/literature/repo

# Make sure the prod compose is up:
docker compose -f docker-compose.prod.yml ps   # web should be (healthy)

# Copy the dump into the bind-mount so the container can read it:
sudo -u deploy cp /tmp/legacy.json data/

# Run the import inside the web container:
docker compose -f docker-compose.prod.yml exec web \
    python manage.py import_legacy_dump --file /app/data/legacy.json
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

- The actual PDF byte payload. Copy `data/media/literature/pdf/` from the legacy host to the new `data/media/literature/pdf/` (e.g. via `rsync`).
- A pre-existing PageHit table on the new install. If you've been running the new site and accumulated hits, the import's `update_or_create(pk=...)` could conflict with new PageHit rows that share a legacy `pk`. In practice this is unlikely (the new install starts at `pk=1` and the legacy table has thousands of rows), but if you want to be paranoid, `psql -c "TRUNCATE pagehit_pagehit;"` before importing.
- Schema migrations for new constraints introduced post-Phase-1. The dump's field shapes have to be compatible with the current model definitions; if a field type narrowed (e.g. `max_length` shrank), some rows might fail.

## Troubleshooting

**`CommandError: Could not parse <path> as JSON`** — the file you pointed at isn't valid JSON. If you accidentally fed it the `.tar.bz2` instead of the extracted JSON, `tar -xjf` it first.

**`CommandError: Expected a JSON array`** — the dump came from a non-`dumpdata` source. The importer expects Django dumpdata format: a top-level JSON array of `{"model": ..., "pk": ..., "fields": ...}` records.

**`UNIQUE constraint failed`** — there's already a row with that legacy `pk` *and different content*. This shouldn't happen with `update_or_create`, but if you've manually crafted Items in the admin with low IDs that collide with the legacy data's, drop them first.

**Subclass record without parent** — `[skip] items.journalpub pk=N: no matching items.item record`. Means the dump is incomplete (the parent Item row is missing). Run `dumpdata` on the legacy DB again, making sure to include `items` (the dump should always pair every subclass row with its `items.item` parent).
