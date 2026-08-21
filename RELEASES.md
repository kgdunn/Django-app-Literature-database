# Releases

## v1.6.3

Two surgical docstring corrections in `items/models.py`; no behaviour
change, no template or API surface touched.

- **`InCollection.full_citation`** (line 640) — the docstring's `Format:`
  example was missing two commas that the code actually emits. The
  method's body renders the parts via `", ".join(parts)` which puts a
  comma between the chapter-title segment and the `in <editors> (eds.),
  "<book title>"` segment, and after the editors' `(eds.)` before the
  book title (verified against
  `items/tests/test_models.py::test_full_citation_renders_eds_suffix_for_editors`
  at line 348). Updated the format line to match: `Author: "Chapter
  title", in Editors (eds.), "Book Title", edition, publisher, pp. X–Y,
  year.`
- **`Author.save`** (line 68) — the docstring said "Strip surrounding
  whitespace from the name fields" (plural), which implies all three
  name fields get stripped. The body only strips `first_name` and
  `last_name` — `middle_initials` is left untouched. Rewrote the
  docstring to name the two fields explicitly and call out that
  `middle_initials` is deliberately excluded, so a future reader isn't
  surprised by whitespace slipping through from that column. Behaviour
  is unchanged.

## v1.6.2

Consolidated docstring/comment corrections, combining the still-applicable
findings from the docstring-audit PR backlog (#119, #124, #126, #132, #133)
into one change. Almost entirely documentation; the one exception is the
removal of the unused `Author.full_name_hyperlinked` property (detailed
below). No user-visible behaviour change either way.

Findings from those PRs that had already been fixed on `main` by v1.6.1
(`Item.author_slugs` examples, the `core_tags` "Submission model" text,
`get_pagehits`'s "half-open" window, and `get_items_or_404`'s PDF wording)
are **not** repeated here — only what was still stale is carried forward.

- **`items/models.py`** — `Item.get_absolute_url` still carried the "I can't
  seem to find a way to use the `reverse` or `permalink` functions"
  docstring even though the body does call `reverse(...)`. Replaced with a
  description of the technique actually in use: resolve `lit-view-item` with
  a placeholder pk of `0`, strip it to leave the route prefix, then append
  the real `<pk>/<slug>` (the slug segment is optional in the URL pattern,
  so a single `reverse()` cannot emit both parts).
- **`items/models.py`** — **removed** the vestigial
  `Author.full_name_hyperlinked` property. Despite the name it returned the
  plain name, byte-for-byte identical to `full_name`, with no anchor tag.
  It was not awaiting an implementation — the hyperlinked rendering it was
  named for already exists as `Item._format_authors_html`
  (`get_absolute_url()` + `full_name` wrapped in an `<a>`), which backs
  `full_author_listing`, `full_editor_listing`, and
  `author_list_all_lastnames` and is covered by `TestFullAuthorListing`.
  Nothing in the repo referenced the property — no view, template, admin
  config, or fixture — so it was a duplicate left behind when the real
  implementation moved to `Item`. Keeping it invited a future caller to
  reach for the misleadingly-named one and silently render an unlinked
  byline.
- **`items/models.py`** — `Author.save`, `School.save`, `Journal.save`, and
  `Publisher.save` all carried the same placeholder docstring consisting of
  a (now-dead) link to the Django docs. Each replaced with a one-liner
  describing what the override actually does. `Journal.save` additionally
  notes that its case-insensitive uniqueness is a DB-level
  `UniqueConstraint` on `Lower("name")`, not something this method checks.
- **`items/views.py`** — `show_items` listed a `"sort"` value for
  `what_view` that no dispatch branch implements (and a matching "sort
  field" note on `extra_info`). Both removed.
- **`items/views.py`** — `view_item` claimed "no PDF download path exists".
  True of Phase 5, but v1.4.0 reintroduced the default-off
  `Item.pdf_is_public` + gated `view_pdf` path. Rewritten to describe the
  flag-gated "View PDF" link.
- **`pages/views.py`** — the `search` docstring described the
  `SearchVector` as covering only title / abstract / other_search_text. The
  issue-#33 work added six subclass-specific fields; all nine are now
  enumerated.
- **`pages/views.py`** — `page_404_error` now documents its `extra_info`
  kwarg (optional human-readable message for the 404 template context,
  falling back to `str(exception)`).
- **`pages/urls.py`** — the `search` route comment claimed a "Postgres FTS
  in prod, icontains fallback in SQLite dev" split. Both settings modules
  target Postgres and the view has no fallback branch; comment corrected.
- **`utils/__init__.py`** — `get_IP_address` referred to `download_item` in
  the present tense; Phase 5 removed that view. Wording corrected.

Also included (not a docstring change, flagged separately for review):

- **`uv.lock`** — regenerated. The committed lock had drifted out of sync
  with `pyproject.toml`: it still pinned `django==5.2.14` and
  `pdfplumber==0.11.9` even though the manifest requires `django>=5.2.16`
  and `pdfplumber>=0.11.10` (PRs #131 and #128 bumped the constraints but
  the lockfile was never regenerated), and its `literature` version entry
  still read `1.6.0` against a `1.6.1` manifest. Running any `uv` command
  reconciles this automatically, so the refresh is picked up here rather
  than left for the next unrelated PR to carry. Transitively this also
  moves `pdfminer-six`, `pypdfium2`, and a handful of dev-only packages
  (`pygments`, `packaging`, `filelock`, …) to the versions the existing
  constraints already resolve to.

PATCH bump. The property removal is the only non-documentation change and
it is dead code with no referents, so there is no user-visible behaviour
change, no URL change, and no schema change — which puts it under "no
user-visible behaviour change" rather than the MAJOR "removal of public
views" clause.

## v1.6.1

Docstring corrections so they match the code's actual behaviour
(documentation-only; no runtime change).

- **`pagehit/views.py`** — `get_pagehits` docstring described the date
  range as "half-open ... both inclusive", which is self-contradictory;
  the implementation uses `__gte` / `__lte`, i.e. a closed interval.
  Rewritten to say "closed window ... both endpoints inclusive".
- **`items/templatetags/core_tags.py`** — `most_searched` and
  `most_viewed` both carried the same wrong docstring ("Get the most
  viewed items from the Submission model"). The `Submission` model
  doesn't exist in this repo, and `most_searched` returns query-string
  strings (not viewed items). Both docstrings rewritten to describe what
  each filter actually returns, and to note that the leading `field`
  argument is unused for `most_searched` (present only so the filter is
  callable from a template).
- **`items/models.py`** — `Item.author_slugs` docstring claimed the
  property was "used to create the PDF file name" and listed dashed
  example outputs (`Smith-and-Weston`, `Joyce-Smith-Smythe`). Neither
  matches the code: PDF filenames are built from `Item.slug` via
  `upload_dest`, and the property joins last names with spaces / commas
  (`Smith and Weston`, `Joyce, Smith and Smythe`). Rewritten to describe
  the NFKD-ASCII fold behaviour and correct the example lines.
- **`items/views.py`** — `get_items_or_404` docstring said "PDFs are no
  longer exposed publicly (copyright restriction)"; v1.4.0 reintroduced a
  narrow default-off public path via `Item.pdf_is_public` + `view_pdf`.
  Rewritten to clarify that this decorator wraps only `view_item`, and
  that `view_pdf` does its own lookup outside the decorator (so this
  sentence is about the decorator's scope, not about global PDF access).
  Also added `InCollection` to the list of subclasses the decorator
  downcasts to.

## v1.6.0

Repeat the item detail page's Previous / Next navigation at the **bottom**
of the page, so a visitor who has scrolled through the citation, abstract,
tags, and related-items panel can move to the adjacent item without
scrolling back up to the top topbar.

- **`items/templates/items/item.html`** — after the related-items section,
  render a second `<nav class="detail-topbar detail-topbar--bottom">`
  carrying just the Previous (left) and Next (right) chips. It reuses the
  same `item.previous_item` / `item.next_item` model properties (pk ± 1) as
  the top topbar, the same `__spacer` placeholder when one side is missing,
  and is wrapped in `{% if item.previous_item or item.next_item %}` so
  nothing renders when there's no neighbour. No "Back to home" chip — that
  stays at the top only.
- **`literature/static/literature/site.css`** — add a `.detail-topbar--bottom`
  rule that flips the topbar's margin to sit below the content. All other
  chip styling (grid, hover, mobile padding) is reused unchanged.

No view, URL, or model changes — the bottom bar reads the existing
`previous_item` / `next_item` properties. MINOR: additive, user-visible
navigation affordance.

## v1.5.2

Make the public-PDF link on the item detail page read as an actual downloadable document instead of a plain text link (operator request).

- **`items/templates/items/item.html`** — the `View PDF` link now leads with an inline-SVG **PDF document icon** (a page with a folded corner and a red "PDF" ribbon). The icon is inline SVG (no extra request, CSP-clean), its outline uses `currentColor` so it tracks the link colour in both light and dark themes, and the ribbon stays PDF-red. The link text and `{% url 'lit-public-pdf' %}` target are unchanged, so the v1.4.0 gating and the "no Download PDF / download.pdf" guarantees still hold.
- **`literature/static/literature/site.css`** — `.lit-pdf-link` (inline-flex, icon + label, hover-underlines the label) and `.lit-pdf-link__icon` sizing.

PATCH bump — cosmetic detail-page polish, no behaviour or URL change.

## v1.5.1

Docstring corrections so they match the code's actual behaviour (documentation-only; no runtime change). Renumbered from the original 1.3.2 in this PR onto the current `main` (now at 1.5.0).

- **`pagehit/views.py`** - `get_pagehits` docstring previously claimed
  the returned list was ordered by ``pk``, but the implementation sorts
  by hit-count and reverses (descending by hits). The rewrite documents
  both the aggregate branch and the ``item_pk``-supplied scalar branch,
  and notes that ``item`` is ignored in the aggregate path.
- **`pagehit/views.py`** - `get_search_hits` docstring now states that
  results are sorted descending by ``n_hits`` and that terms are
  ASCII-folded/profanity-filtered before counting.
- **`pagehit/views.py`** - a misleading inline comment (``# extra_info=None
  to avoid counting download hits``) above the aggregate ORM filter was
  replaced; that filter does not look at ``extra_info`` at all.
- **`tagging/views.py`** - `get_tag_uses` docstring corrected: the list
  is sorted descending by ``n_uses``, not by ``Tag.pk``.
- **`items/views.py`** - `show_items` docstring expanded to document the
  ``what_view`` / ``extra_info`` parameters that drive the per-branch
  queryset and template.

## v1.5.0

Vendor MathJax + ECharts as local static assets and drop `cdn.jsdelivr.net` from the CSP (issue #79, security-audit umbrella #86). `script-src` is now a bare `'self'` — no third-party script CDN — which shrinks the XSS surface and removes a runtime dependency on jsDelivr's edge.

- **Vendored bundles** under `literature/static/literature/vendor/` (served from `/static`):
  - `tex-mml-svg.js` — **MathJax 3.2.2, SVG output**. MathJax 2.7.9 (the old CDN pin) can't be self-hosted as a single file — `MathJax.js` lazy-loads its config/extensions/fonts at runtime (~63 MB npm package). The v3 SVG bundle is one ~2 MB file with every glyph embedded as an SVG path, so it fetches **zero** files at runtime (no web fonts either). Inline `\(...\)` / display `\[...\]` / `$$...$$` delimiters unchanged; rendering is visually equivalent.
  - `echarts.min.js` — Apache ECharts 5.5.1 (the tag/author sparkline), previously CDN-loaded.
  - `README.md` — provenance (source URLs, versions, SHA-256s) + refresh/upgrade steps.
- **MathJax config** moved to `literature/static/literature/mathjax-config.js` (a static file, not an inline `<script>`) so the CSP stays free of `'unsafe-inline'`.
- **CSP** (`literature/middleware.py`): `script-src 'self'` (was `'self' https://cdn.jsdelivr.net`). Google Fonts (`style-src`/`font-src`) are the only remaining off-origin allowances.
- **SRI dropped** for these assets — redundant for same-origin files served over the page's own TLS. The now-unused `make sri` target is removed.
- **Tests**: `test_csp_script_src_is_self_only_no_cdn` pins the tightened header; `test_no_jsdelivr_and_local_mathjax_in_rendered_html` and `test_sparkline_page_loads_local_echarts` pin that the rendered HTML references the local bundles and never `cdn.jsdelivr.net`. Existing sparkline tests updated off the old SRI assertion.
- **Docs**: CLAUDE.md `base.html` description + a Tooling "Vendored front-end assets" maintenance reminder (refresh the bundles ~every 6 months, folded into whatever PR is in flight — Dependabot can't bump them), `docs/SECURITY.md` (audit row 6 → Fixed), and a `Last vendored:` date in the vendor `README.md`.

Note: the MathJax bundle embeds two `cdn.jsdelivr.net` URLs for the opt-in Speech Rule Engine (screen-reader Explorer). These are never fetched during normal rendering and are blocked by `connect-src 'self'` if a visitor manually enables the Explorer — graceful degradation, documented in the vendor `README.md`.

Also closes #72 (robots.txt + staging noindex) in the audit ledger — the feature shipped earlier and is test-covered; this PR marks it done in `docs/SECURITY.md`.

MINOR bump — dependency vendoring + CSP tightening + MathJax major-version bump, no URL/template-structure change and visually-equivalent math rendering.

## v1.4.0

Per-item "show this PDF publicly" admin override. Operator brief: the catalogue holds copyright-restricted PDFs that must never be downloadable (the Phase-5 rule), but one or two entries are openly-licensed public documents that *should* be viewable. This adds a default-off checkbox so those specific items — and only those — expose their PDF.

What landed:

- **`items.Item.pdf_is_public`** — a new `BooleanField(default=False)`. Off for every existing item (migration `0011_item_pdf_is_public_alter_item_pdf_file`), so the catalogue's default-deny posture is preserved: a PDF is only ever served once an admin explicitly ticks the box for a copyright-cleared document.
- **`items.view_pdf`** (URL name `lit-public-pdf`, route `/item/<id>/pdf`) — a gated view that streams `Item.pdf_file` inline (`Content-Type: application/pdf`, `as_attachment=False`). It 404s unless the item has `pdf_is_public=True` **and** a `pdf_file`. Registered before the `lit-view-item` catch-all so the path isn't swallowed as a slug.
- **Detail page** (`items/templates/items/item.html`) — renders a "View PDF" link only when the item is flagged public and has a PDF. The Phase-5 forbidden strings ("Download PDF", "download.pdf") are never reintroduced.
- **Admin** (`items/admin.py`) — `pdf_is_public` added to the `Item` change-list display and a `list_filter`, so the handful of public items are easy to find and audit. The checkbox auto-appears on every Item/JournalPub/Book/Thesis/etc. edit form (no `fields` restriction).
- **About page** — updated to note that a small number of openly-licensed documents are viewable via the per-item "View PDF" link.
- **Production**: the Caddy `/media/literature/pdf/*` 404 **stays** — public PDFs are served only through `view_pdf` in the gunicorn worker, never the static path, so the in-DB flag remains the single gate (`docs/deploy.md` updated).
- **Hardening (defense-in-depth)**: the on-disk PDF path is the guessable `literature/pdf/<slug[0]>/<slug>.pdf` shape (slug = public title), so downloading one public PDF could otherwise let a visitor reconstruct the media URL of a *non-public* item. `literature/urls.py` now registers a `_block_media_pdf` view that hard-404s `^media/literature/pdf/` ahead of the `DEBUG`-only `static()` media handler — mirroring the Caddy rule inside Django so dev / staging / any infra change can't leak a PDF either. The gated `view_pdf` is the only route to PDF bytes in every environment. Tests pin: id-enumeration can't leak a private PDF (and the 404 is not an existence oracle), and the raw slug-derived media path 404s even when the attacker knows the exact slug.
- **Tests**: new `TestPublicPdfOverride` class in `items/tests/test_views.py` pins the default-deny invariant — flag-off (with or without a PDF) 404s, flag-on + PDF serves inline `%PDF` bytes, the detail-page link appears iff public. The existing `TestNoPdfDownloadEndpoint` guarantees (dead `lit-download-pdf` name, `/item/<id>/download.pdf` redirect) still hold.
- **Docs**: CLAUDE.md gotcha #3 + Project shape + views list rewritten from "PDFs are not downloadable. Period." to "admin-only by default; the only public path is the gated `pdf_is_public` override."

MINOR bump — additive feature + schema addition, default-off, no behaviour change for any existing item.

## v1.3.1

Sibling-palette of v1.3.0 Steel-teal — same brief (de-matrix the theme), but drops teal entirely for a deep navy. Operator merged v1.3.0 Steel-teal first; this PR is the side-by-side comparison option that branched from main *after* Steel-teal merged, so it inherits all of v1.3.0's mono→sans chip styling and only changes the palette.

Palette diff vs v1.3.0:

| Token | v1.3.0 Steel-teal | v1.3.1 Oxford navy |
|---|---|---|
| Light accent | ``#155e75`` washed teal | ``#1f4e7a`` Oxford navy |
| Light focus | ``#0891b2`` (cyan) | ``#2563eb`` (blue) |
| Dark accent | ``#67b8c5`` washed teal-cyan | ``#7ea2c4`` soft navy |
| Dark bg | ``#161b1f`` warm slate (teal undertone) | ``#161b22`` warm slate (navy undertone) |
| Dark surface | ``#1e252b`` | ``#1e252e`` |

Mono→sans chip swaps, layout, templates, URLs — all unchanged from v1.3.0.

If the operator prefers this navy variant after the side-by-side, this PR replaces v1.3.0 cleanly (forward-version bump). If they prefer the teal variant, this PR just gets closed without merging — v1.3.0 stays.

- **``pyproject.toml``** / **``RELEASES.md``**: PATCH bump within the 1.3.x line (same theme rework as v1.3.0, just a different colour family).

## v1.3.0

De-matrix the site theme. Operator brief: the v1.2.x palette + monospace chip buttons + near-black dark mode read as "old-school computery, like the Matrix", and the site audience is business professionals with a light academic bend — softer, more journal-like is the target.

This PR is one of two parallel options. The other ("Oxford navy") drops teal entirely for a deep navy. This one ("Steel-teal") keeps the teal lineage but desaturates and adds slate so the palette still reads as the same site, just less neon.

Changes (all in ``literature/static/literature/site.css``):

1. **Light-mode accent**: ``#0e7c7b`` (vivid teal) → ``#155e75`` (steel teal, ~Tailwind ``cyan-800``). Hover, link, soft-bg, accent-soft-fg, focus all shift to match. Page bg shifts a hair warmer (``#fafaf7`` → ``#f7f7f4``) and text-muted/subtle pick up a slate cast so they read less "tropical".

2. **Dark-mode accent**: ``#5eead4`` (mint-cyan, neon) → ``#67b8c5`` (washed teal-cyan). Dark bg shifts from the near-black dark-teal ``#0a1414`` to a warm slate ``#161b1f``. This is the single biggest "de-matrix" lever — the v1.2.x dark mode was literally Matrix-palette (cyan-on-black); v1.3.0 reads like a "premium reading-mode" (warm slate with a desaturated teal accent).

3. **Mono → sans on every chip-style element**:
   * ``.theme-toggle`` ("DARK" / "AUTO" pill in the header) — adds ``font-weight: 600`` to keep the visual weight.
   * ``.lit-tag`` — accent-soft tag chips (search results, detail-page Tags row). ``font-weight: 500``.
   * ``.lit-year-list a`` — Browse-by-year chips on the front page.
   * ``.detail-topbar__btn`` + ``.lit-page-back__link`` — the Prev / Home / Next chips at the top of every detail page and the Back-to-home chip on every list / search / tag / about page.
   * ``.lit-year-nav a`` — prev/next year on the per-year listing.

   Mono is **kept** only where it carries information (numeric / tabular):
   * ``.lit-items-table .col-year`` (tabular numerics)
   * ``.lit-related__year`` (small numeric year annotation)
   * ``.lit-pagination`` ("page X of Y" — keeps the digits aligned)

Layout, templates, URLs all unchanged. Tag-cloud anchor font (``Arial``) unchanged — the cloud was a deliberate departure from the IBM Plex stack and reads as a distinct visual unit.

- **``pyproject.toml``** / **``RELEASES.md``**: MINOR bump per the policy in ``CLAUDE.md`` (visible theme change visitor-wide; no URL or template-structure break).

## v1.2.4

Centre the single "Back to home" chip on list / search / tag / all-tags / about pages so it sits in the same horizontal position as the centre ``__home`` button in the detail-page topbar's three-button row. v1.2.2 had landed it left-aligned, which read as a miss between the two surfaces: detail pages had a centred home button, list pages had a left-aligned one.

- **``literature/static/literature/site.css``** — ``.lit-page-back { text-align: center; }``. One declaration; the chip is ``display: inline-flex`` so it respects the wrapper's ``text-align``.
- **``pyproject.toml``** / **``RELEASES.md``**: PATCH bump.

**Cache note for the operator**: Cloudflare proxies ``literature.learnche.org`` and caches ``/static/*`` for a few hours by default, so CSS changes shipped here can appear "not landed" on a phone for up to ~4 h after the deploy completes. If a fresh visual check on a mobile device shows the previous version, force-refresh (Chrome mobile: long-press the reload button → *Empty cache and hard reload*; iOS Safari: Settings → Safari → Clear History) or wait for the Cloudflare edge cache to expire. A more permanent fix is to switch ``STATICFILES_STORAGE`` to ``ManifestStaticFilesStorage`` so the asset URL changes per content hash and bypasses cache deterministically — tracked as a separate issue, not part of this PR.

## v1.2.3

Re-balance the homepage hero search bar for mobile after operator caught it eating ~25% of viewport height on a phone (v1.2.2 had the input at 72 px tall **and** stacked above a 72 px button — ~156 px of vertical real estate before the visitor saw any other content).

New responsive curve, all inside ``literature/static/literature/site.css``:

| Viewport | Input font | Input height | Layout |
|---|---|---|---|
| Desktop ≥ 769 px | 2 rem (32 px) | 96 px | input + button side-by-side |
| Tablet ≤ 768 px | 1.375 rem (22 px, ≈ h3) | 60 px | side-by-side |
| Phone ≤ 480 px | 1.125 rem (18 px) | 48 px | side-by-side |

Key changes vs v1.2.2:

- The 640 px breakpoint moves out to 768 px and brings the size down further (60 px tall, h3-sized font).
- The 480 px breakpoint **stops stacking** input above button — a 380-400 px phone has plenty of room for ~210 px input + 8 px gap + ~108 px button on one row, and not stacking saves ~108 px of vertical space (one full row's worth).
- Phone sizing drops to a normal touchable input (48 px tall, 18 px font) — still clearly the primary action above the fold, but no longer dominates the page.

Knock-on: placeholder text "Search all references — title, abstract, author, journal, tag…" truncates earlier on narrow phones. That's normal mobile-search UX (visitors tap the field and the placeholder vanishes); accepting the truncation is the cost of the smaller bar.

Desktop is unchanged — the 96 px / 32 px hero treatment from v1.2.1 stays put.

- **``pyproject.toml``** / **``RELEASES.md``**: PATCH bump (responsive-CSS tweak; no template-structure or URL change).

## v1.2.2

Visual-consistency follow-up after v1.2.1. The chip-button "Back to home" affordance landed on the detail page, but the search / tag / list / about pages still rendered the old plain teal-link version (a hold-over from the v1.0.0 chrome). On the same site this read as two different sites — operator caught it on the tag results page.

v1.2.2 brings the four remaining non-detail pages onto the same chip-button styling so the back affordance reads identically everywhere.

- **``items/templates/items/show-entries.html``** (list / tag-results / author-results / journal-results / pub-by-year), **``items/templates/items/show-tag-cloud.html``** (full tag cloud), **``pages/templates/pages/search.html``** (search results), **``pages/templates/pages/about-page.html``** (about): each replaces ``<p class="detail-topbar"><a>← Back to home</a></p>`` with ``<p class="lit-page-back"><a class="lit-page-back__link">← Back to home</a></p>``.
- **``literature/static/literature/site.css``** — ``.detail-topbar__btn`` style rule grouped with ``.lit-page-back__link`` (and same for the ``:hover`` rule) so there's a single source of chip-button truth; new ``.lit-page-back`` wrapper (margin only) and ``.lit-page-back__link`` modifier (font-weight + slightly more padding) so the standalone back chip reads as the page-anchor affordance.
- **``pyproject.toml``** / **``RELEASES.md``**: PATCH bump (cosmetic, no template-structure or URL change — the back link still goes to ``/`` from the same position at the top of every page).

The detail-page topbar (three buttons in a CSS-grid row, ``.detail-topbar`` and ``.detail-topbar__btn--prev/--home/--next``) is unchanged.

## v1.2.1

Tune the v1.2.0 UX changes after operator feedback:

1. **Hero search bar roughly doubled in size.** v1.2.0's hero search still read as "a regular input box" — the font went from `--fs-sm` (14 px) to `1.125rem` (18 px) and the height from a default-ish ~38 px to 56 px. v1.2.1 bumps the desktop font to `2rem` (32 px) and the min-height to 96 px — the input is now bigger than every heading on the site and there is no ambiguity about the primary action. A `@media (max-width: 640px)` rule backs it down to `1.5rem` / 72 px on phones so the placeholder text doesn't truncate.
2. **Detail-page topbar redesigned as three matching chip-buttons in one row.** v1.2.0's layout (plain "Back to home" link on the left, accent-soft pill chips for prev/next on the right) confused visitors — the three affordances looked like two different kinds of thing and on narrow viewports the row wrapped into a stacked mess. v1.2.1 lays them out as **[← Previous] [Back to home] [Next →]** in a CSS-grid (1fr / auto / 1fr), all three styled identically as chips, with the centre "Back to home" carrying a slightly heavier font-weight to read as the group anchor. An aria-hidden `__spacer` fills the grid cell when prev or next is missing so the centre button stays geometrically centred even at the corpus boundaries.

Changes:

- **``items/templates/items/item.html``** — `.detail-topbar` becomes a `<nav>` containing three `__btn` elements (or `__spacer` fillers when the neighbour doesn't exist). The earlier `__back` / `__pager` / `__pager-link` selectors are gone.
- **``literature/static/literature/site.css``** —
  * `.lit-search--hero` input: `font-size: 2rem`, `min-height: 96px`, `padding: var(--sp-5) var(--sp-6)`, larger box-shadow. Submit button matched: `min-height: 96px`, `font-size: 1.25rem`. New `@media (max-width: 640px)` scales both back to `1.5rem` / 72 px so a long placeholder stays readable on phones; the existing `@media (max-width: 480px)` still stacks input + button when the viewport gets very narrow.
  * `.detail-topbar` rewritten as a 3-column CSS grid (`grid-template-columns: 1fr auto 1fr`). New `.detail-topbar__btn` chip with `--prev` / `--home` / `--next` modifiers — all three share the same accent-soft chip styling so a visitor can't mistake one for another. `.detail-topbar__btn--home` carries `font-weight: 600` so the centre button reads as the group anchor. New `.detail-topbar__spacer` is the aria-hidden empty filler for missing neighbour cells. A `@media (max-width: 420px)` rule shrinks the chip padding so all three still fit in one row on 360 px viewports.
- **``items/tests/test_views.py``** — the two `TestItemDetail` v1.2.0 tests rewritten to match the new selectors:
  * ``test_top_pager_renders_before_title`` — checks all three of `__btn--prev` / `__btn--home` / `__btn--next` render with the right labels, asserts the topbar appears before the `<h3>` title, and asserts both the pre-v1.2.0 `.lit-detail-nav` and the v1.2.0 transitional `__pager` selectors are gone.
  * ``test_top_pager_suppressed_for_solo_item`` — for a single-item DB, asserts `__btn--prev` / `__btn--next` are absent, `__btn--home` is present, and exactly **two** `__spacer` elements fill the missing grid cells (one for each side of home).
- **``pyproject.toml``** / **``RELEASES.md``**: PATCH bump per the policy in ``CLAUDE.md`` (this PR is a follow-up tuning of v1.2.0's visible behaviour, not a new feature surface).

Visitor impact (after deploy): the homepage search bar is now hard to miss, and the three navigation affordances on every detail page are laid out as a clear row of equal-weight buttons with the home anchor in the middle — even on narrow viewports.

## v1.2.0

Two homepage / detail-page UX changes lifted from operator feedback after the v1.1.0 abstract roll-out:

1. **Homepage search is now the hero.** The search form moved above the "A collection of references on latent-variable methods…" intro, the input grew (taller, bigger font, accent-soft focus ring, subtle shadow), and the placeholder is more inviting ("Search all references — title, abstract, author, journal, tag…"). The intro paragraph stays as a one-line subtitle below the bar.
2. **Prev/next item navigation hoisted to the detail-page top bar.** Previously the prev/next links sat at the bottom of every detail page — past the abstract + tags + related-items panel — so stepping between items required a scroll-to-bottom every time. The pager is now in the top bar alongside ``Back to home``, rendered as accent-soft pill chips that read as a distinct affordance (no risk of mistaking them for the back link).

Changes:

- **``pages/templates/pages/front-page.html``** — search form moved above the site-statement; placeholder text expanded; form gains the ``lit-search--hero`` modifier class. The intro paragraph keeps its text but gains the ``lit-site-statement--subtitle`` modifier so it reads as supporting prose rather than a parallel-weight card.
- **``items/templates/items/item.html``** — the ``detail-topbar`` block changes from a single ``<a>`` to a flex container holding ``detail-topbar__back`` on the left and a ``detail-topbar__pager`` ``<nav aria-label="Item navigation">`` on the right (pager block is suppressed entirely when the item has no neighbours, no empty container). The old bottom ``<nav class="lit-detail-nav">`` is removed.
- **``literature/static/literature/site.css``** —
  * New ``.lit-search--hero`` rules (larger padding, 1.125rem font, ``var(--radius-lg)`` corners, ``box-shadow``, ``min-height: 56px`` on both input and button so they line up, an explicit ``@media (max-width: 480px)`` stack so neither shrinks below a usable tap target).
  * ``.detail-topbar`` becomes a flex container (``justify-content: space-between``); new ``.detail-topbar__back`` and ``.detail-topbar__pager`` rules. ``.detail-topbar__pager-link`` is a pill chip styled with ``--color-accent-soft`` / ``--color-accent-soft-fg`` so it's visually distinct from the plain-link back affordance.
  * New ``.lit-site-statement--subtitle`` modifier drops the card chrome (border / background / left-accent stripe), shrinks the text, and caps the line length at 60ch so the subtitle reads as one-line prose.
  * The unused ``.lit-detail-nav`` block (matching the now-removed bottom nav) is deleted; a short comment in its place points at ``.detail-topbar__pager`` for future maintainers.
- **``items/tests/test_views.py``** — two new ``TestItemDetail`` tests pin the new behaviour:
  * ``test_top_pager_renders_before_title`` — pager markup is present *and* its position in the rendered HTML is before ``<h3>{title}</h3>``; ``.lit-detail-nav`` is asserted **not** present (so a future regression that re-adds a bottom pager gets caught).
  * ``test_top_pager_suppressed_for_solo_item`` — when an item has no prev/next neighbour, the pager block is omitted (no empty container, no orphan ``aria-label``); ``Back to home`` still renders.
- **``pyproject.toml``** / **``RELEASES.md``**: MINOR bump per the policy in ``CLAUDE.md`` (additive / cosmetic public-page change; no URL break, no removal of public views, no template-structure break that would surprise a casual visitor).

Visitor impact: the search bar is now the obvious primary action on the homepage, and stepping between adjacent items on the detail page no longer requires scrolling to the bottom.
## v1.1.1

Raise the Python line-length convention from 88 (black's default) to 120 across the toolchain, and reformat the codebase to match. Pure mechanical change; no behavioural, schema, URL, or template impact. Motivated by repeated friction wrapping new test signatures and call sites to fit under 88 — at 120 most one-liners stay readable on modern displays and black stops fighting human-natural call composition.

- **`pyproject.toml`** — new `[tool.black]` and `[tool.isort]` sections, each pinning `line-length = 120` / `line_length = 120`. Black auto-picks this up; isort needs both `--profile black` (other style defaults) **and** an explicit length override (the `black` profile would otherwise clamp it back to 88).
- **`.flake8`** — `max-line-length` raised from 100 to 120 so the lint stage matches the formatters.
- **`.pre-commit-config.yaml`** — isort hook gains `--line-length 120` after `--profile black` (CLI overrides config-file precedence); blacken-docs hook gains `--line-length 120`; black hook unchanged (it reads `[tool.black]` from `pyproject.toml`). Each change has a short rationale comment so a future maintainer doesn't "tidy" them away.
- **`CLAUDE.md`** — Tooling section's flake8 bullet rewritten to call out the unified line-length policy across black + isort + blacken-docs + flake8, with the gotcha about the isort-profile-black clamp made explicit.
- **Codebase reformat** — `black --line-length 120` and `isort --profile black --line-length 120` run across the repo (excluding `(items|tagging|pagehit)/migrations/` as the pre-commit `exclude:` already does). 19 source files reflowed; net diff -294 / +98 lines, almost entirely existing multi-line signatures and call sites collapsing to single lines under the new limit. Black's "magic trailing comma" rule kept any block that already had a trailing comma multi-line, so the per-arg-per-line shape stays everywhere it existed.
- **`pyproject.toml`** / **`RELEASES.md`**: PATCH bump (infra-only tooling tweak + cosmetic reformat; no user-visible behaviour change), per the policy in `CLAUDE.md`.

The companion change in the openmv stack (`kgdunn/Django-dataset-download-app`) is intentionally **not** part of this PR — the operator opted to keep the scope to literature for now. If we want to mirror the convention there later, it's a one-shot follow-up of the same shape.

## v1.1.0

Show article abstracts on the detail page by default. Previously, every
detail page suppressed the abstract behind ``Item.show_abstract``, which
defaulted to ``False`` and was never flipped to ``True`` for the
imported legacy corpus. Abstracts existed in the DB (FTS already
indexed them — they were searchable but invisible on the actual item
page) and never reached the reader. The 2010-era design intended
``show_abstract`` as an admin opt-in gate, but the revived site has no
review workflow that would flip it, so it had become a permanent "off"
switch for every abstract on the site. Drop the field entirely; gate
on ``Item.abstract`` content in the template instead.

- **`items/templates/items/item.html`** — the abstract block now gates
  on ``{% if item.abstract %}`` instead of ``{% if item.show_abstract %}``.
  Rendering pipeline (bleach allowlist + MathJax for ``\(...\)``)
  unchanged.
- **`items/models.py`** — ``Item.show_abstract`` field declaration
  removed. If a specific abstract ever needs hiding, clear the
  ``abstract`` field instead.
- **`items/migrations/0010_remove_item_show_abstract.py`** — new
  migration drops the column. Standard
  ``ALTER TABLE items_item DROP COLUMN show_abstract``; reversible via
  the operation's auto-generated inverse.
- **`items/admin.py`** — no changes needed; ``show_abstract`` was
  never on ``ItemAdmin.list_display`` or ``fields``.
- **`items/tests/conftest.py`** — ``journalpub_factory`` no longer
  passes ``show_abstract=True`` (the kwarg would now raise
  ``TypeError: got an unexpected keyword argument`` since the field
  is gone).
- **`items/tests/test_views.py`** — two ad-hoc ``objects.create``
  calls (in ``test_journal_name_in_search_vector`` and
  ``test_conference_name_in_search_vector``) drop the
  ``show_abstract`` kwarg. Two new ``TestItemDetail`` tests pin the
  new behaviour:
  ``test_abstract_renders_when_non_empty`` (abstract content surfaces
  under a ``<dt>Abstract</dt>`` block) and
  ``test_abstract_section_omitted_when_empty`` (empty abstract
  produces no Abstract header, no empty ``<dd>``).
- **`items/tests/test_import_legacy_dump.py`** — fixture and test
  comments updated: ``"show_abstract": True`` in legacy JSON now joins
  the silently-dropped-field set, alongside the Phase-5
  ``private_pdf`` / ``can_show_pdf`` and Phase-4 ``ua_string`` /
  ``ip_address`` fields. The existing
  ``test_dropped_fields_are_silently_ignored`` covers the path.
- **`CLAUDE.md`** — Project shape / Models entry no longer lists
  ``show_abstract`` among ``Item`` fields; Templates / Gotchas
  updated to describe the new ``{% if item.abstract %}`` gate; a
  pointer in Gotcha 5 tells the future maintainer to clear the
  ``abstract`` field rather than reintroduce a ``show_abstract``-style
  boolean.
- **`pyproject.toml`** / **`RELEASES.md`** — MINOR bump per the
  policy in ``CLAUDE.md`` (additive visible behaviour change on a
  public page: abstract content that was suppressed now appears for
  every item that has it; no URL change, no template-structure break).

**Visitor impact**: every article-detail page now surfaces the
abstract inline below the citation block, wrapped in the same bleach
allowlist + MathJax rendering pipeline used elsewhere. Items without
an abstract (``blank=True``) render as before — no extra heading.

## v1.0.3

Bugfix + runbook for the 2026-05-10 live-site incident. Two unrelated failures stacked: Caddy on the shared Hetzner host had a JSON config hot-pushed to its admin API on `localhost:2019` that 403'd every request with `Host not in allowlist` (custom `x-deny-reason: host_not_allowed` header), and once that was unblocked, every DB-touching page 500'd because `pagehit_pagehit.id`'s Postgres sequence was still at 1 — a latent bomb left by Phase 10's `import_legacy_dump`, which writes rows with explicit legacy pks but never bumped the sequences afterwards. `pages.healthz` was the only view that didn't trigger the integrity error, which masked the second failure for over an hour.

- **`items/management/commands/import_legacy_dump.py`** — append a `_reset_sequences` step at the end of every non-dry-run import. Captures `manage.py sqlsequencereset items pagehit tagging` into a `StringIO`, then executes the resulting `setval(...)` statements against the live connection in one cursor call. Idempotent: running it on an empty result set is a no-op. The import command stays inside its own `transaction.atomic()` for the row inserts; the sequence reset runs after the commit so a rolled-back dry run leaves sequences untouched. Closes the live-site bomb for any future imports against this command.
- **`docs/deploy.md`** — new `## Troubleshooting` section with the two failure-mode runbooks: the Caddy admin-API override (symptom + `admin off` + restart fix) and the stale `pagehit` sequence (symptom + `sqlsequencereset … | dbshell` one-shot). Future-you reads these and recovers in one shot instead of an hour of grep.
- **`pyproject.toml`** / **`RELEASES.md`** — PATCH bump per `CLAUDE.md`'s policy (a behavioural bugfix in the import command + a doc addition; no template, URL, dependency, or schema change).

The Caddy `admin off` change is server-side only — applied on the Hetzner host as part of the incident response, not version-controlled in this repo (the Caddyfile lives in `/etc/caddy/` outside any git tree). The runbook in `docs/deploy.md` is the durable record of what was done.

## v1.0.2

Documentation: rename the off-host backup S3 bucket from `openmv-backups`
to `kgd-backups` in docs and the `bin/backup-literature.sh` header
comment, reflecting the actual shared-bucket name used in production.
The bucket itself was renamed when the live backup setup was wired up on
the Hetzner host on 2026-05-10; this PR brings the docs in sync. The
script reads the bucket name from `$BACKUP_S3_BUCKET` in `.env`, so no
runtime / CI / template / dependency change.

- **`docs/backup.md`** — every reference to `openmv-backups` (intro
  paragraph, S3 layout block, IAM policy ARNs in 1b, `.env` example
  block, verify / restore commands, real-disaster-recovery commands,
  troubleshooting) updated to `kgd-backups`.
- **`CLAUDE.md`** — Backups-section parenthetical now reads
  ``(`kgd-backups`)`` instead of ``(`openmv-backups`)``.
- **`bin/backup-literature.sh`** — header comment example for
  `BACKUP_S3_BUCKET` updated. Runtime behaviour unchanged; the script
  reads the bucket name from `.env`.
- **`pyproject.toml`** / **`RELEASES.md`**: PATCH bump (docs +
  comment, no user-visible behaviour change), per the policy in
  `CLAUDE.md`.
- The matching docs rename in the openmv stack
  (`kgdunn/Django-dataset-download-app`) is shipped in a sibling PR
  on the same branch name.

## v1.0.1

Supply-chain modernization: migrate the Postgres driver from
`psycopg2-binary` (legacy, feature-frozen as of 2024) to `psycopg[binary]`
(psycopg3, actively maintained, native-async, type-aware). Issue #85;
mirrors openmv's audit finding #13. Also a pre-req for Phase 12 pgvector
which prefers psycopg3.

- `pyproject.toml` — `psycopg2-binary>=2.9.12` →
  `psycopg[binary]>=3.1,<4`. Re-locked via `uv lock`.
- `Dockerfile` runtime stage — `libpq5` removed from the apt install
  list. `psycopg[binary]` ships a self-contained binary wheel that
  bundles its own libpq, so the system package is no longer needed.
  Trims a couple of MB from the runtime image.

Django 5.2 supports both psycopg2 and psycopg3 transparently; no
`DATABASES` config change needed. Django wraps driver exception
classes in `django.db.utils.*`, so application code is unaffected.

## v1.0.0

First tagged release of the revived `literature.learnche.org`. Captures the multi-PR 2026 modernization of the original 2010-era Django 1.11 / Python 2 codebase that was defunct mid-2010s. The site is now Django 5.2 LTS / Python 3.11 / Postgres / Docker on Hetzner, behind Caddy + Cloudflare, with a privacy-respecting view counter, a Postgres-FTS search backend, and S3 nightly backups.

### Phases landed

The revival was sequenced as 11 phases plus the `master` → `main` rename, each shipping as its own PR:

- **Phase 0** (#1) — repo hygiene baseline. `CLAUDE.md`, `pyproject.toml` (uv), `Makefile`, pre-commit, `.gitignore`, `.editorconfig`, `.flake8`, `.python-version` (3.11), `.dockerignore`, `.env.example`, `docs/legacy-todo.md` archive.
- **Master → main rename** (#2) — default-branch rename with corresponding doc updates.
- **Phase 1** (#3) — Python 2 → 3 + Django 1.11 → 5.2 port. `unicode()` → `str()`, `cStringIO` → `io.BytesIO`, `from django.core.urlresolvers` → `django.urls`, `url()` → `re_path()`, `render_to_response(..., RequestContext)` → `render(...)`, explicit `on_delete=` on every FK, `pdfminer` → `pdfplumber`, `mimetype=` → `content_type=`, `is_authenticated()` → `is_authenticated`. Dropped the `local_settings.py` shim and the haystack imports.
- **Phase 2** (#4) — settings split + `SecurityHeadersMiddleware` + `.env`-driven config. `literature/settings/{base,dev,prod,ci}.py`. `env()` / `env_list()` helpers reading `os.environ` first then `.env`. `SECRET_KEY` mandatory. CSP / Permissions-Policy / Cross-Origin-Opener-Policy on every response. Production-only HSTS, secure cookies, `X-Frame-Options: DENY`, Caddy proxy headers.
- **Phase 3** (#5) — drop Haystack, add Postgres FTS. `pages.search` rewritten with `SearchVector` (title-A / abstract-B / other_search_text-C) + `SearchRank` + `TrigramSimilarity > 0.3` on author last names. `search_type='websearch'` so `-foo` excludes and quoted phrases preserve order. New migration `items/0004_pg_trgm` installs the `pg_trgm` extension. **Dev now runs against Postgres** (not SQLite) so the FTS / trigram code paths are exercised the same way locally and in production.
- **Phase 4 + Phase 5** (#6, combined) — privacy / copyright cleanup.
  - PageHit PII trim: `ua_string` and `ip_address` columns dropped via `pagehit/0003_drop_pagehit_pii`. The schema now holds only `(id, datetime, item, item_pk, extra_info)` — privacy-safe to retain indefinitely. Admin is read-only (append-only audit log).
  - The legacy IP-allowlist gate on `download_item` removed (it was security-theatre behind Cloudflare's edge-IP rewrite).
  - Public PDF download path **removed entirely** (copyright restriction). `items.download_item` and the `lit-download-pdf` URL pattern are gone; `Item.private_pdf` and `Item.can_show_pdf` flags dropped via `items/0005_drop_pdf_visibility_flags`. PDFs remain admin-uploaded archival storage, consumed only by `__extract_extra__` for FTS extraction.
  - New `items/templatetags/extra_tags.py` with `sanitise_markup` template filter — bleach allowlist over `Item.abstract` (`a, b, i, em, strong, sub, sup, code, br, p, span, ul, ol, li, dl, dt, dd`).
- **Phase 6** (#7) — templates modernization. `templates/base.html` rewritten with IBM Plex design tokens (light + dark theme via `prefers-color-scheme` + `data-theme`), tri-state theme toggle persisted in `localStorage`, mobile-first viewport, **SRI-pinned MathJax 2.7.9** from `cdn.jsdelivr.net`. Front page got a 5-portal layout (Recently added / Tag cloud / Most viewed / **Browse by year** / Top search terms). Detail page is a `<dl>` meta layout that grids on ≥600 px and stacks on mobile. Items table reflows into cards under 768 px. CSP shrunk: dropped `cdnjs.cloudflare.com` from the `script-src` allowlist.
- **Phase 7** (#8) — Dockerize. Multi-stage `Dockerfile` (uv builder + `python:3.11-slim` runtime, runs as UID 1000 `app`, gunicorn on `:8000`, `HEALTHCHECK` curls `/healthz`). `docker-compose.yml` for dev with a Postgres sidecar + `runserver` hot-reload. `docker-compose.prod.yml` for prod, loopback-only on offset ports `127.0.0.1:8002` (web) / `127.0.0.1:5435` (db) — coexists with the openmv stack on the same Hetzner host. New `pages.healthz` view (plain-text `ok`, `Cache-Control: no-store`, no DB hit).
- **Phase 8** (#9 + a fixup) — tests + CI workflow + Dependabot. 35 tests in `items/tests/` (14 model + 21 view, including security-header presence and the negative tests pinning the no-public-PDF-download guarantee). `.github/workflows/ci.yml` boots a `postgres:16-alpine` service container (digest-pinned), runs pre-commit + pytest + non-blocking pip-audit. Third-party actions SHA-pinned. `.github/dependabot.yml` for weekly `github-actions` + `docker` ecosystem bumps. The fixup commit added a global `exclude:` for migrations to `.pre-commit-config.yaml` and cleared a long tail of pre-existing flake8 debt that the first CI run surfaced.
- **Phase 9** (#11) — Hetzner deploy automation + bootstrap runbook. `bin/deploy-impl.sh` (host-side: `docker compose up -d --build` + sanity-curl `127.0.0.1:8002/healthz`). `.github/workflows/deploy.yml` SSHes to Hetzner via a forced-command key. `docs/deploy.md` is the full one-time host-bootstrap runbook (Cloudflare DNS, Origin Cert, Caddy server block with `/media/literature/pdf/*` 404 guard, SSH deploy key, GitHub repo secrets).
- **Phase 10** (#39 + #40) — legacy data import. `manage.py import_legacy_dump --file <path>` consumes a Django `dumpdata --all` JSON snapshot from the connectmv.com / Mercurial-era 2010-2018 install. Idempotent (legacy `pk`s preserved via `update_or_create`); handles multi-table inheritance, M2M, `AuthorGroup`, the `media/` prefix on `Item.pdf_file`, and the Phase-4/5 dropped fields. 11 new tests. `docs/data-import.md` is the runbook (later corrected in #40 to use `docker cp …:/tmp/` instead of an unreachable bind-mount path).
- **Phase 11** (#41) — S3 nightly backups. `bin/backup-literature.sh` runs nightly under `deploy` from cron at 22:35 UTC (one hour offset from openmv's 21:35). Three things: `pg_dump` of the `db` container → `db/daily/`, monthly + yearly promotions, retention pruning (15 / 12 / ∞); `aws s3 sync` of `data/media/` (the PDF library — irreplaceable) and `data/public/`; **without `--delete`** so an accidental local rm or detached bind-mount doesn't propagate off-host. Sharing the existing `openmv-backups` bucket via the `literature/` prefix with a separate IAM user. `docs/backup.md` is the full one-time AWS + Hetzner bootstrap runbook with restore drill and disaster-recovery section.

### Phase 15 itself (this release)

- **`RELEASES.md`** — this file. Authoritative release record going forward.
- **`.github/workflows/release.yml`** — auto-tags + creates a GitHub Release whenever the version in `pyproject.toml` changes on `main` and there is a matching `## v<version>` section here. Mirrors openmv's release pipeline (SHA-pinned `actions/checkout`).
- **`.github/workflows/deploy.yml`** — **gated on CI success.** Trigger changed from `push: branches: [main]` to `workflow_run: workflows: ["CI"], types: [completed], branches: [main]` with a job-level `if` filter requiring `github.event.workflow_run.conclusion == 'success'`. A failed CI run no longer deploys. `workflow_dispatch` (manual rollback / forced redeploy) still fires unconditionally.
- **`pyproject.toml`** version bumped `0.1.0` → `1.0.0`.

### Versioning

From here the project follows semver:

- **PATCH** — bugfixes, dependency security bumps, infra-only tweaks with no user-visible behaviour change.
- **MINOR** — additive features, schema additions, new templates, new settings modules, CI parity work.
- **MAJOR** — URL or template structure breaks, removal of public views, anything that could surprise an unsuspecting visitor.

Every PR after this release should bump `pyproject.toml` `version` and add a matching `## v<new-version>` section to this file. The release workflow refuses to run if the heading is missing — that's the safety net.

### How v1.0.0 was tagged

The Phase 15 PR bumped `pyproject.toml` `version` to `1.0.0` and added this section. Once that PR merged to `main`, `.github/workflows/release.yml` auto-detected the version change and published the GitHub Release.
