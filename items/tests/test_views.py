"""Smoke tests for the public-facing views.

Covers the routes that have to keep working through every revival phase:
front page, about, item-detail, item-list, search (Postgres FTS +
trigram fuzzy author lookup), healthz, and 404 path. Also has a couple
of negative tests that pin Phase-5's "no public PDF download" guarantee.
"""

import pytest
from django.urls import NoReverseMatch, reverse


@pytest.mark.django_db
class TestStaticPages:
    def test_front_page_returns_200(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert b"Recently added" in r.content
        assert b"Browse by year" in r.content

    def test_about_page_returns_200(self, client):
        r = client.get("/about")
        assert r.status_code == 200

    def test_about_page_mentions_mistake_reporting(self, client):
        # Issue #21: the about page tells visitors how to report a
        # wrong-author / missing-tag / broken-DOI etc.
        r = client.get("/about")
        assert b"mistake" in r.content.lower() or b"mistakes" in r.content.lower()
        # And the email address is the reporting channel.
        assert b"kgdunn@gmail.com" in r.content

    def test_healthz_returns_200_with_no_store(self, client):
        for path in ("/healthz", "/healthz/"):
            r = client.get(path)
            assert r.status_code == 200, path
            assert r.content == b"ok"
            assert r["Cache-Control"] == "no-store"

    def test_footer_copyright_renders_year_range(self, client):
        # The footer's copyright is a year *range* "2010 – <current
        # year>", with the right-hand year auto-updating via Django's
        # ``{% now "Y" %}`` tag so the notice never goes stale at the
        # turn of a year.
        from datetime import date

        r = client.get("/")
        body = r.content.decode("utf-8")
        # En-dash separator, NOT hyphen — consistent year-range typography.
        assert "&copy; 2010 &ndash;" in body or "© 2010 –" in body
        assert str(date.today().year) in body

    def test_robots_txt_returns_text_plain_with_admin_disallow(self, client):
        # Issue #72: /robots.txt keeps /admin/ out of search-engine
        # indexes. Served by Django so the file lives in the repo and
        # tracks the URL surface (no Caddy config to drift).
        r = client.get("/robots.txt")
        assert r.status_code == 200
        assert r["Content-Type"].startswith("text/plain")
        body = r.content.decode("utf-8")
        assert "User-agent: *" in body
        assert "Disallow: /admin/" in body
        assert "Disallow: /accounts/" in body
        assert "Disallow: /__extract_extra__/" in body


@pytest.mark.django_db
class TestStagingNoindex:
    """Issue #72: when LITERATURE_NOINDEX is truthy (set in the
    staging .env), every response carries an ``X-Robots-Tag: noindex,
    nofollow`` header so search engines leave the staging hostname
    alone. Production deploys leave the setting unset / false and use
    the per-path ``Disallow`` rules in /robots.txt instead."""

    def test_header_emitted_when_setting_true(self, client, settings):
        settings.LITERATURE_NOINDEX = True
        r = client.get("/")
        assert r.get("X-Robots-Tag") == "noindex, nofollow"

    def test_header_omitted_when_setting_false(self, client, settings):
        settings.LITERATURE_NOINDEX = False
        r = client.get("/")
        assert r.get("X-Robots-Tag") is None

    def test_header_omitted_when_setting_unset(self, client):
        # Default: setting absent. Middleware uses ``getattr(...,
        # False)``; no header should be emitted.
        r = client.get("/")
        assert r.get("X-Robots-Tag") is None


@pytest.mark.django_db
class TestSecurityHeaders:
    def test_csp_present_on_front_page(self, client):
        r = client.get("/")
        csp = r.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_csp_script_src_is_self_only_no_cdn(self, client):
        # Issue #79: MathJax + ECharts are vendored under /static, so the
        # CSP no longer allows cdn.jsdelivr.net. script-src is a bare
        # 'self'. Pins against a regression that re-adds a CDN allowance.
        r = client.get("/")
        csp = r.get("Content-Security-Policy", "")
        assert "cdn.jsdelivr.net" not in csp
        assert "script-src 'self';" in csp

    def test_csp_drops_unsafe_inline(self, client):
        # Issue #80: the inline <style> + <script> blocks were extracted
        # into ``literature/static/literature/{site.css, theme-preload.js,
        # theme-toggle.js, sparkline.js}`` so the CSP can refuse inline
        # script and style execution. A future regression that re-adds
        # an inline ``<script>...</script>`` block in any template would
        # show up as a browser-side CSP violation; this test pins the
        # header so a *settings* regression (someone re-adding
        # 'unsafe-inline' to bypass the issue) gets caught at CI time.
        r = client.get("/")
        csp = r.get("Content-Security-Policy", "")
        assert "'unsafe-inline'" not in csp
        assert "'unsafe-eval'" not in csp

    def test_no_jsdelivr_and_local_mathjax_in_rendered_html(self, client):
        # Issue #79: every page (base.html) must load MathJax from /static,
        # never cdn.jsdelivr.net. Guards against a template regression that
        # would silently re-introduce the CDN dependency.
        r = client.get("/")
        body = r.content
        assert b"cdn.jsdelivr.net" not in body
        assert b"/static/literature/vendor/tex-mml-svg.js" in body

    def test_sparkline_page_loads_local_echarts(self, client, journalpub_factory, author):
        # Issue #79: the tag/author sparkline must load ECharts from
        # /static. The sparkline only renders when the filtered set spans
        # >1 year, so seed two years for the same author.
        journalpub_factory(authors=[author], title="Early", year=2019)
        journalpub_factory(authors=[author], title="Later", year=2024)
        r = client.get(f"/item/author/{author.slug}/")
        assert r.status_code == 200
        assert b"cdn.jsdelivr.net" not in r.content
        assert b"/static/literature/vendor/echarts.min.js" in r.content

    def test_permissions_policy_present(self, client):
        r = client.get("/")
        assert "interest-cohort=()" in r.get("Permissions-Policy", "")

    def test_coop_present(self, client):
        r = client.get("/")
        assert r.get("Cross-Origin-Opener-Policy") == "same-origin"


@pytest.mark.django_db
class TestItemDetail:
    def test_canonical_url_returns_200(self, client, journalpub_factory, author, tag):
        pub = journalpub_factory(authors=[author], tags=[tag], title="Test paper")
        r = client.get(f"/item/{pub.pk}/{pub.slug}")
        assert r.status_code == 200
        assert b"Test paper" in r.content
        assert b"Einstein" in r.content
        # Phase 5 guarantee: no public PDF download UI on the page.
        assert b"Download PDF" not in r.content
        assert b"download.pdf" not in r.content

    def test_no_slug_redirects_to_canonical(self, client, journalpub_factory, author):
        pub = journalpub_factory(authors=[author])
        r = client.get(f"/item/{pub.pk}/")
        assert r.status_code == 301
        assert r["Location"].endswith(f"/item/{pub.pk}/{pub.slug}")

    def test_unknown_item_returns_404(self, client):
        r = client.get("/item/999/")
        assert r.status_code == 404

    def test_incollection_detail_renders(self, client, incollection_factory, author):
        """Theme D: a book-chapter detail page resolves and shows
        the chapter + book titles via full_citation."""
        chap = incollection_factory(authors=[author], title="A chapter title")
        r = client.get(f"/item/{chap.pk}/{chap.slug}")
        assert r.status_code == 200
        body = r.content.decode("utf-8")
        assert "A chapter title" in body
        # Book title is italicised in the citation.
        assert "Multivariate Statistical Methods for Process Modelling" in body

    def test_related_items_panel_shows_overlapping_titles(self, client, journalpub_factory, author):
        """Issue #36: the detail page surfaces a small list of items
        most similar (by FTS title+abstract overlap) to the current
        one. A paper with overlapping subject vocabulary should appear;
        an unrelated paper should not.
        """
        target = journalpub_factory(
            authors=[author],
            title="Process monitoring with multivariate methods",
            abstract="<p>Latent-variable diagnostics for batch processes.</p>",
        )
        related = journalpub_factory(
            authors=[author],
            title="Multivariate methods for process diagnostics",
            abstract="<p>Latent variables and SPC.</p>",
        )
        unrelated = journalpub_factory(
            authors=[author],
            title="Bayesian inference for ecology",
            abstract="<p>Population dynamics and MCMC.</p>",
        )

        r = client.get(f"/item/{target.pk}/{target.slug}")
        assert r.status_code == 200
        body = r.content.decode("utf-8")
        assert "Related items" in body
        assert related.title in body
        assert unrelated.title not in body
        # Self-link guarded at the queryset level
        # (Item.objects.exclude(pk=item.pk) in _get_related_items).
        # No external assertion needed — the target's title appears 3×
        # in any item-detail page via the <title>, the <h3> heading,
        # and full_citation, none of which are the related list.

    def test_related_items_panel_omitted_when_no_overlap(self, client, journalpub_factory, author):
        """No overlap with any other item → no panel rendered."""
        target = journalpub_factory(authors=[author], title="Solo paper on a unique topic")
        # Single item in the DB → nothing else to relate to.
        r = client.get(f"/item/{target.pk}/{target.slug}")
        assert r.status_code == 200
        # The CSS class lives in base.html's <style> block on every page,
        # so check for the rendered <section> heading instead.
        assert "<h4>Related items</h4>" not in r.content.decode("utf-8")

    def test_abstract_renders_when_non_empty(self, client, journalpub_factory, author):
        """v1.1.0: the legacy ``Item.show_abstract`` gate was dropped.
        The template now renders the abstract whenever the field has
        content, wrapped in the bleach allowlist + MathJax pipeline."""
        pub = journalpub_factory(
            authors=[author],
            title="Paper with an abstract",
            abstract="<p>Latent-variable methods for batch monitoring.</p>",
        )
        r = client.get(f"/item/{pub.pk}/{pub.slug}")
        assert r.status_code == 200
        body = r.content.decode("utf-8")
        assert "<dt>Abstract</dt>" in body
        assert "Latent-variable methods for batch monitoring." in body

    def test_abstract_section_omitted_when_empty(self, client, journalpub_factory, author):
        """v1.1.0: ``Item.abstract`` is ``blank=True``; if empty, the
        template skips the <dt>Abstract</dt> / <dd> block entirely (no
        empty header, no empty <dd>)."""
        pub = journalpub_factory(
            authors=[author],
            title="Paper with no abstract",
            abstract="",
        )
        r = client.get(f"/item/{pub.pk}/{pub.slug}")
        assert r.status_code == 200
        body = r.content.decode("utf-8")
        assert "<dt>Abstract</dt>" not in body

    def test_top_pager_renders_before_title(self, client, journalpub_factory, author):
        """v1.2.1: detail-page top bar is a three-button row —
        [← Previous] [Back to home] [Next →] — rendered above the
        title so visitors don't have to scroll to step between items.
        All three share the same chip styling so it's unambiguous
        which is which (the v1.2.0 mixed-styling cut had users
        clicking the wrong link)."""
        # Three consecutive items so the middle one has both prev + next
        # via Item.previous_item / Item.next_item (which look up pk±1).
        journalpub_factory(authors=[author], title="Item-before-target")
        target = journalpub_factory(authors=[author], title="Target paper")
        journalpub_factory(authors=[author], title="Item-after-target")

        r = client.get(f"/item/{target.pk}/{target.slug}")
        assert r.status_code == 200
        body = r.content.decode("utf-8")

        # All three buttons render with distinct modifier classes.
        assert "detail-topbar__btn--prev" in body
        assert "detail-topbar__btn--home" in body
        assert "detail-topbar__btn--next" in body
        assert "&larr; Previous" in body
        assert "Back to home" in body
        assert "Next &rarr;" in body

        # Position: the topbar appears *before* the item title.
        topbar_pos = body.find('class="detail-topbar"')
        title_pos = body.find(f"<h3>{target.title}</h3>")
        assert topbar_pos != -1, "detail-topbar markup missing"
        assert title_pos != -1, "Title <h3> missing"
        assert topbar_pos < title_pos, f"Topbar (at {topbar_pos}) should render before the title (at {title_pos})."

        # Old bottom-of-page nav (pre-v1.2.0) and the v1.2.0 transitional
        # selectors are both gone.
        assert "lit-detail-nav" not in body
        assert "detail-topbar__pager" not in body

    def test_top_pager_suppressed_for_solo_item(self, client, journalpub_factory, author):
        """v1.2.1: when an item has no previous / next neighbour the
        prev/next chips are suppressed, but a hidden ``__spacer`` fills
        each missing grid cell so the centre ``Back to home`` button
        stays geometrically centred."""
        target = journalpub_factory(authors=[author], title="Solo paper")
        r = client.get(f"/item/{target.pk}/{target.slug}")
        assert r.status_code == 200
        body = r.content.decode("utf-8")
        # Home is always present.
        assert "detail-topbar__btn--home" in body
        # Prev/next chips are NOT rendered for a solo item.
        assert "detail-topbar__btn--prev" not in body
        assert "detail-topbar__btn--next" not in body
        # Two spacers fill the prev + next grid cells so home stays centred.
        assert body.count("detail-topbar__spacer") == 2


@pytest.mark.django_db
class TestSearch:
    def test_empty_query_redirects_to_front_page(self, client):
        r = client.get("/search?q=")
        assert r.status_code == 302
        assert r["Location"] == "/"

    def test_title_match(self, client, journalpub_factory, author):
        journalpub_factory(authors=[author], title="On the Fourier transform")
        r = client.get("/search?q=fourier")
        assert r.status_code == 200
        assert b"On the Fourier transform" in r.content

    def test_abstract_match(self, client, journalpub_factory, author):
        journalpub_factory(
            authors=[author],
            title="A different paper",
            abstract="<p>Wave-function collapse on superconducting qubits.</p>",
        )
        r = client.get("/search?q=qubits")
        assert r.status_code == 200
        assert b"A different paper" in r.content

    def test_author_exact(self, client, journalpub_factory, author):
        journalpub_factory(authors=[author], title="Some paper")
        r = client.get("/search?q=Einstein")
        assert r.status_code == 200
        assert b"Some paper" in r.content

    def test_author_trigram_typo(self, client, journalpub_factory, author):
        """`einstien` (typo of Einstein) still resolves via TrigramSimilarity > 0.3."""
        journalpub_factory(authors=[author], title="Some paper")
        r = client.get("/search?q=einstien")
        assert r.status_code == 200
        assert b"Some paper" in r.content

    def test_no_match_renders_empty_state(self, client, journalpub_factory, author):
        journalpub_factory(authors=[author], title="Fourier")
        r = client.get("/search?q=zzqxzzqx")
        assert r.status_code == 200
        assert b"No items match" in r.content

    def test_numeric_id_shortcut(self, client, journalpub_factory, author):
        """A numeric `q` that matches an Item.pk redirects to the detail page."""
        pub = journalpub_factory(authors=[author])
        r = client.get(f"/search?q={pub.pk}")
        assert r.status_code == 302
        assert r["Location"].rstrip("/").endswith(f"/item/{pub.pk}")

    def test_exact_title_returns_own_item(self, client, journalpub_factory, author):
        """Regression for issue #15: typing an exact title (with hyphenated
        terms and English stop words) should return that item.

        Reproduces the legacy report: the query "Process Monitoring and
        Diagnosis by Multi-Block" did not return the item titled exactly
        that. Two suspect mechanics, both worth pinning:

        1. ``websearch_to_tsquery('english', ...)`` ANDs bare terms after
           stemming + stop-word removal, so "Process Monitoring and
           Diagnosis by Multi-Block" should reduce to roughly
           ``process & monitor & diagnos & multi & block`` — a strict
           subset of the title's own SearchVector tokens.
        2. Hyphenated terms (``Multi-Block``) are tokenized into two
           lexemes by the english config, but only if both vector and
           query tokenize them the same way.

        If this test fails, the failure mode tells us which side is the
        culprit.
        """
        journalpub_factory(
            authors=[author],
            title="Process Monitoring and Diagnosis by Multi-Block PCA and PLS Models",
        )
        r = client.get("/search?q=Process+Monitoring+and+Diagnosis+by+Multi-Block")
        assert r.status_code == 200
        assert b"Process Monitoring and Diagnosis by Multi-Block" in r.content

    def test_hyphenated_word_in_query(self, client, journalpub_factory, author):
        """Narrower probe: hyphenated single term in query should match a
        title that also contains the hyphenated term."""
        journalpub_factory(authors=[author], title="Multi-Block PLS overview")
        r = client.get("/search?q=multi-block")
        assert r.status_code == 200
        assert b"Multi-Block PLS overview" in r.content

    def test_journal_name_in_search_vector(self, client, db):
        """Issue #33: a query matching the journal name finds JournalPubs
        in that journal even if title/abstract don't contain the word.
        """
        from items.models import Author, AuthorGroup, Journal, JournalPub

        author = Author.objects.create(first_name="Svante", last_name="Wold")
        analytica = Journal.objects.create(name="Analytica Chimica Acta", website="https://example.com/aca")
        # Title and abstract intentionally don't contain "Analytica".
        pub = JournalPub.objects.create(
            title="Calibration in chemometrics",
            item_type="journalpub",
            year=2010,
            abstract="<p>Latent-variable methods for spectroscopic data.</p>",
            journal=analytica,
        )
        AuthorGroup.objects.create(author=author, item=pub, order=0)

        r = client.get("/search?q=Analytica")
        assert r.status_code == 200
        assert b"Calibration in chemometrics" in r.content

    def test_isbn_in_search_vector(self, client, book_factory, author):
        """Issue #33: search by ISBN returns the matching Book."""
        book_factory(authors=[author], title="An obscure-titled book", isbn="9781234567890")
        r = client.get("/search?q=9781234567890")
        assert r.status_code == 200
        assert b"An obscure-titled book" in r.content

    def test_book_title_finds_incollection(self, client, incollection_factory, author):
        """Theme D / #33 follow-up: a query against the parent book's
        title returns the InCollection chapter, even though the chapter's
        own title doesn't contain the term."""
        incollection_factory(
            authors=[author],
            title="A specific chapter on PCA",
            book_title="Statistical methods in chemometrics",
        )
        r = client.get("/search?q=chemometrics")
        assert r.status_code == 200
        assert b"A specific chapter on PCA" in r.content

    def test_conference_name_in_search_vector(self, client, db):
        """Issue #33: search by conference name returns the matching
        ConferenceProceeding."""
        from items.models import Author, AuthorGroup, ConferenceProceeding

        author = Author.objects.create(first_name="John", last_name="MacGregor")
        proc = ConferenceProceeding.objects.create(
            title="Some unique-titled paper",
            item_type="conferenceproc",
            year=2014,
            abstract="<p>About process monitoring.</p>",
            conference_name="MACC Annual Meeting",
            organization="McMaster",
            location="Hamilton, ON",
        )
        AuthorGroup.objects.create(author=author, item=proc, order=0)

        r = client.get("/search?q=MACC")
        assert r.status_code == 200
        assert b"Some unique-titled paper" in r.content

    def test_multi_author_item_not_duplicated_in_results(self, client, journalpub_factory, three_authors):
        """Regression: a multi-author item used to render 2–3× in the
        search results because the ``TrigramSimilarity`` annotation
        joins through ``AuthorGroup → Author`` and produces one row per
        author. The queryset's ``.distinct()`` couldn't collapse them:
        each joined row had a different ``author_sim`` value (the
        trigram for that specific author's last name), and Postgres'
        ``SELECT DISTINCT`` considers every column in the SELECT list
        — different ``author_sim`` → different row → no dedup.

        Wrapping the trigram in ``Max()`` forces a ``GROUP BY`` on
        Item.id, so each item produces one row with the max similarity
        across its authors.
        """
        pub = journalpub_factory(
            authors=three_authors,
            title="Multi-author paper on Fourier transforms",
        )
        r = client.get("/search?q=fourier")
        assert r.status_code == 200
        body = r.content.decode("utf-8")
        target_link = f"/item/{pub.pk}/{pub.slug}"
        occurrences = body.count(target_link)
        assert occurrences == 1, f"Item appeared {occurrences}× in results (expected 1)"

    def test_exact_title_ranks_above_distractors(self, client, journalpub_factory, author):
        """Issue #15 follow-up: on the live site, an exact-title query
        returns the matching item but it ranked ~12th because the default
        SearchRank (Postgres ``ts_rank``) is frequency-based. A paper
        whose ``other_search_text`` repeats "monitoring" / "process"
        dozens of times scores higher than a paper whose **title** says
        those words once, even though title has weight A and
        other_search_text has weight C — frequency × weight beats a
        single high-weight occurrence.

        Switching to ``cover_density=True`` (Postgres ``ts_rank_cd``)
        scores by query-term proximity instead. An exact phrase in the
        title scores near 1.0 because the terms are adjacent; scattered
        mentions across an extracted-PDF body score much lower.
        """
        # The target: exact phrase in its own title (weight A).
        target = journalpub_factory(
            authors=[author],
            title="Process Monitoring and Diagnosis by Multi-Block PCA and PLS Models",
            year=2008,
        )

        # Distractors: each one mentions the query terms many times in
        # ``other_search_text`` (weight C) but does NOT have the phrase
        # in its title. Without cover-density ranking, ts_rank's
        # frequency boost pushes these above the target.
        distractor_body = (
            "monitoring monitoring monitoring process process diagnosis " "diagnosis multi block multi block. " * 30
        )
        for i in range(11):
            journalpub_factory(
                authors=[author],
                title=f"Unrelated paper {i}",
                other_search_text=distractor_body,
                year=2024,  # newer than target — also a tiebreaker risk
            )

        # Pre-flight: the 12 items genuinely exist in the DB; this isn't
        # an empty-corpus pass.
        from items.models import Item

        assert Item.objects.count() == 12

        r = client.get("/search?q=Process+Monitoring+and+Diagnosis+by+Multi-Block")
        assert r.status_code == 200

        # The target's title must appear before any "Unrelated paper"
        # heading in the rendered page. cover_density is allowed to
        # *filter the distractors out entirely* (their ts_rank_cd on a
        # weight-C-only body match is below the rank__gt=0 threshold) —
        # that's a stronger fix than just reordering. The bad outcome
        # we're guarding against is the pre-fix one: target ranked
        # below distractors that frequency-boosted ahead of it.
        target_phrase = b"Process Monitoring and Diagnosis by Multi-Block"
        target_pos = r.content.find(target_phrase)
        first_distractor_pos = r.content.find(b"Unrelated paper")
        assert target_pos != -1, "Target not present in results at all"
        assert first_distractor_pos == -1 or target_pos < first_distractor_pos, (
            f"Target ranked below distractors: target at {target_pos}, " f"first distractor at {first_distractor_pos}"
        )
        assert target.title.encode() in r.content


@pytest.mark.django_db
class TestNoPdfDownloadEndpoint:
    """Phase 5 hard rule: no *unconditional* public PDF download URL exists.

    The narrow, default-off `pdf_is_public` override (see
    `TestPublicPdfOverride`) is the only sanctioned way to expose a PDF, and
    it doesn't resurrect the old `lit-download-pdf` name or the
    `/item/<id>/download.pdf` path.
    """

    def test_lit_download_pdf_url_name_does_not_resolve(self):
        with pytest.raises(NoReverseMatch):
            reverse("lit-download-pdf", args=[1])

    def test_legacy_download_pdf_path_redirects_to_canonical(self, client, journalpub_factory, author):
        """Stale links like `/item/1/download.pdf` now match the catch-all
        `lit-view-item` regex with slug='download' and 301-redirect to the
        canonical detail URL — no PDF served at any point.
        """
        pub = journalpub_factory(authors=[author])
        r = client.get(f"/item/{pub.pk}/download.pdf")
        assert r.status_code == 301
        # Redirect target ends with the canonical slug, NOT '.pdf'.
        assert r["Location"].endswith(f"/item/{pub.pk}/{pub.slug}")
        assert ".pdf" not in r["Location"]


# A tiny but structurally-valid PDF body, enough for FileResponse to stream.
_MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


@pytest.mark.django_db
class TestPublicPdfOverride:
    """The default-off `Item.pdf_is_public` admin override and its gated
    `view_pdf` endpoint (`lit-public-pdf`).

    Default-deny is the invariant: a PDF is only ever served when an admin
    has explicitly ticked the box for that item.
    """

    @staticmethod
    def _attach_pdf(factory, author, **kwargs):
        from django.core.files.uploadedfile import SimpleUploadedFile

        pdf = SimpleUploadedFile("doc.pdf", _MINIMAL_PDF, content_type="application/pdf")
        return factory(authors=[author], pdf_file=pdf, **kwargs)

    def test_no_pdf_no_flag_404s(self, client, journalpub_factory, author):
        """No PDF attached and flag off (default) → 404."""
        pub = journalpub_factory(authors=[author])
        assert pub.pdf_is_public is False  # default-off invariant
        r = client.get(reverse("lit-public-pdf", args=[pub.pk]))
        assert r.status_code == 404

    def test_pdf_present_but_flag_off_404s(self, client, journalpub_factory, author, settings, tmp_path):
        """A PDF is attached but the admin has NOT ticked public → 404.
        This is the copyright-default case and the one that must never leak.
        """
        settings.MEDIA_ROOT = str(tmp_path)
        pub = self._attach_pdf(journalpub_factory, author)  # pdf_is_public defaults False
        r = client.get(reverse("lit-public-pdf", args=[pub.pk]))
        assert r.status_code == 404

    def test_flag_on_serves_pdf_inline(self, client, journalpub_factory, author, settings, tmp_path):
        """Flag ticked + PDF attached → 200 with the PDF bytes, inline."""
        settings.MEDIA_ROOT = str(tmp_path)
        pub = self._attach_pdf(journalpub_factory, author, pdf_is_public=True)
        r = client.get(reverse("lit-public-pdf", args=[pub.pk]))
        assert r.status_code == 200
        assert r["Content-Type"] == "application/pdf"
        # as_attachment=False → shown inline in the browser, not force-downloaded.
        assert r.get("Content-Disposition", "inline").startswith("inline")
        assert b"".join(r.streaming_content).startswith(b"%PDF")

    def test_flag_on_without_file_404s(self, client, journalpub_factory, author):
        """Flag ticked but no PDF uploaded → still 404 (nothing to serve)."""
        pub = journalpub_factory(authors=[author], pdf_is_public=True)
        r = client.get(reverse("lit-public-pdf", args=[pub.pk]))
        assert r.status_code == 404

    def test_unknown_item_404s(self, client):
        r = client.get(reverse("lit-public-pdf", args=[999999]))
        assert r.status_code == 404

    def test_id_enumeration_cannot_leak_a_private_pdf(self, client, journalpub_factory, author, settings, tmp_path):
        """Hardening: an attacker who downloads a *public* PDF and then walks
        the id space (`/item/1/pdf`, `/item/2/pdf`, …) only ever gets bytes
        for items the admin actually flagged public. Private neighbours 404,
        and the 404 is indistinguishable from "no such item", so the endpoint
        is not even an existence oracle.
        """
        settings.MEDIA_ROOT = str(tmp_path)
        public = self._attach_pdf(journalpub_factory, author, title="Open access paper", pdf_is_public=True)
        private = self._attach_pdf(journalpub_factory, author, title="Restricted paper")  # flag off

        assert client.get(reverse("lit-public-pdf", args=[public.pk])).status_code == 200
        assert client.get(reverse("lit-public-pdf", args=[private.pk])).status_code == 404
        # Same 404 shape for a private item and a non-existent id (no oracle).
        assert client.get(reverse("lit-public-pdf", args=[private.pk])).content == (
            client.get(reverse("lit-public-pdf", args=[10**9])).content
        )

    def test_raw_media_pdf_path_is_not_served_by_django(self, client, journalpub_factory, author, settings, tmp_path):
        """Hardening: the guessable on-disk path
        `/media/literature/pdf/<slug[0]>/<slug>.pdf` must never be served
        directly. Production blocks it in Caddy; `_block_media_pdf` mirrors
        that inside Django (dev/staging). Even knowing a public item's exact
        slug-derived path, the raw media URL 404s — the gated `view_pdf` is
        the only door.
        """
        settings.MEDIA_ROOT = str(tmp_path)
        pub = self._attach_pdf(journalpub_factory, author, title="Open paper", pdf_is_public=True)
        # Reconstruct the exact path an attacker would guess from the slug.
        guessed = "/media/literature/pdf/%s/%s.pdf" % (pub.slug[0], pub.slug)
        assert client.get(guessed).status_code == 404

    def test_block_media_pdf_view_raises_404(self):
        """The defence-in-depth guard raises Http404 for any pdf-subtree hit."""
        from django.http import Http404

        from literature.urls import _block_media_pdf

        with pytest.raises(Http404):
            _block_media_pdf(None, path="o/anything.pdf")

    def test_detail_page_shows_pdf_link_only_when_public(self, client, journalpub_factory, author, settings, tmp_path):
        """The 'View PDF' link appears on the detail page iff the item is
        flagged public AND has a PDF — and never reintroduces the Phase-5
        forbidden 'Download PDF' / 'download.pdf' strings.
        """
        settings.MEDIA_ROOT = str(tmp_path)
        private = self._attach_pdf(journalpub_factory, author, title="Private paper")
        public = self._attach_pdf(journalpub_factory, author, title="Public paper", pdf_is_public=True)

        r_priv = client.get(f"/item/{private.pk}/{private.slug}")
        assert b"View PDF" not in r_priv.content
        assert b"Download PDF" not in r_priv.content
        assert b"download.pdf" not in r_priv.content

        r_pub = client.get(f"/item/{public.pk}/{public.slug}")
        assert b"View PDF" in r_pub.content
        assert reverse("lit-public-pdf", args=[public.pk]).encode() in r_pub.content
        assert b"Download PDF" not in r_pub.content


@pytest.mark.django_db
class TestItemList:
    def test_show_all_returns_200(self, client, journalpub_factory, author):
        journalpub_factory(authors=[author])
        r = client.get("/item/show-all")
        assert r.status_code == 200

    def test_pub_by_year_filters(self, client, journalpub_factory, author):
        journalpub_factory(authors=[author], title="Y2024", year=2024)
        journalpub_factory(authors=[author], title="Y2023", year=2023)
        r = client.get("/item/pub-by-year/2024/")
        assert r.status_code == 200
        assert b"Y2024" in r.content
        assert b"Y2023" not in r.content

    def test_pub_by_year_renders_prev_next_links(self, client, journalpub_factory, author):
        # Issue #17: closest neighbouring years that have items get
        # prev/next links above the entries list.
        journalpub_factory(authors=[author], year=2008)
        journalpub_factory(authors=[author], year=2010)
        journalpub_factory(authors=[author], year=2024)

        r = client.get("/item/pub-by-year/2010/")
        assert r.status_code == 200
        body = r.content.decode("utf-8")
        # Both prev (2008) and next (2024) should appear as links.
        assert "lit-year-nav" in body
        assert "/item/pub-by-year/2008/" in body
        assert "/item/pub-by-year/2024/" in body

    def test_pub_by_year_no_prev_when_oldest(self, client, journalpub_factory, author):
        # Oldest year → only "next" link, no "prev".
        journalpub_factory(authors=[author], year=2008)
        journalpub_factory(authors=[author], year=2024)

        r = client.get("/item/pub-by-year/2008/")
        assert r.status_code == 200
        body = r.content.decode("utf-8")
        assert "/item/pub-by-year/2024/" in body
        assert "lit-year-nav__prev" not in body  # no prev link

    def test_tag_page_renders_sparkline(self, client, journalpub_factory, author, tag):
        # Issue #27: tag-results page shows an interactive ECharts
        # sparkline of article counts per year above the entries list.
        # (Originally inline SVG; switched to ECharts so hover shows
        # year + article count.)
        journalpub_factory(authors=[author], tags=[tag], year=2008)
        journalpub_factory(authors=[author], tags=[tag], year=2010)
        journalpub_factory(authors=[author], tags=[tag], year=2024)

        r = client.get(f"/item/tag/{tag.slug}/")
        assert r.status_code == 200
        body = r.content.decode("utf-8")
        # Assert on the rendered <div ...>, not the bare class name —
        # the latter also appears in base.html's inline <style> block
        # on every page (same trap PR #55 hit with .lit-tag-description).
        assert '<div class="lit-sparkline-wrap"' in body
        # ECharts mount point + data carrier.
        assert '<div id="lit-sparkline"' in body
        assert 'id="lit-sparkline-data"' in body
        # ECharts loaded from the self-hosted /static vendor path (issue
        # #79); no CDN, no SRI attr (same-origin asset).
        assert "/static/literature/vendor/echarts.min.js" in body

    def test_tag_page_omits_sparkline_when_single_year(self, client, journalpub_factory, author, tag):
        # Only one year of data → wrapper suppressed via the template's
        # ``{% if sparkline_data|length > 1 %}`` guard. The whole
        # ECharts script tag is suppressed too — non-sparkline pages
        # don't pay the load cost.
        journalpub_factory(authors=[author], tags=[tag], year=2024)

        r = client.get(f"/item/tag/{tag.slug}/")
        assert r.status_code == 200
        body = r.content.decode("utf-8")
        assert '<div class="lit-sparkline-wrap"' not in body
        assert "echarts.min.js" not in body

    def test_tag_filter(self, client, journalpub_factory, author, tag):
        journalpub_factory(authors=[author], tags=[tag], title="Has Fourier tag")
        journalpub_factory(authors=[author], title="No tag")
        r = client.get(f"/item/tag/{tag.slug}/")
        assert r.status_code == 200
        assert b"Has Fourier tag" in r.content
        assert b"No tag" not in r.content

    def test_tag_results_renders_description_block(self, client, journalpub_factory, author, db):
        """Issue #12: a tag's description (if set) renders as a small
        block at the top of the per-tag results page."""
        from tagging.models import Tag

        tagged = Tag.objects.create(
            name="Fourier methods",
            description="Spectral and harmonic analysis tools.",
        )
        journalpub_factory(authors=[author], tags=[tagged], title="Hit")

        r = client.get(f"/item/tag/{tagged.slug}/")
        assert r.status_code == 200
        assert b"Spectral and harmonic analysis tools." in r.content
        # The rendered <div ...> element, not the CSS-class definition
        # which lives in base.html's inline <style> on every page.
        assert b'<div class="lit-tag-description">' in r.content

    def test_tag_results_omits_description_block_when_blank(self, client, journalpub_factory, author, tag):
        """No description set → no rendered block; just the entries list."""
        journalpub_factory(authors=[author], tags=[tag])
        r = client.get(f"/item/tag/{tag.slug}/")
        assert r.status_code == 200
        assert b'<div class="lit-tag-description">' not in r.content


@pytest.mark.django_db
class TestTagCloud:
    """Issue #34 + #38 + #12: tag-cloud rendering on the homepage and the
    /item/show/all-tags/ page."""

    def test_cloud_anchor_carries_description_as_title(self, client, journalpub_factory, author, db):
        """Hover-tooltip via the standard ``title=`` attr (#12).
        Falls back to the tag's name when no description is set so
        the hover is never empty."""
        from tagging.models import Tag

        tagged = Tag.objects.create(
            name="Spectroscopy",
            description="Light-matter interaction techniques.",
        )
        journalpub_factory(authors=[author], tags=[tagged])

        r = client.get("/item/show/all-tags/")
        assert r.status_code == 200
        assert b'title="Light-matter interaction techniques."' in r.content

    def test_cloud_anchor_renders_count_superscript(self, client, journalpub_factory, author, db):
        """Per-tag entry count rendered as a small superscript next to
        the name (#38). Three items tagged → ``<sup ...>3</sup>``."""
        from tagging.models import Tag

        tagged = Tag.objects.create(name="Optics")
        for i in range(3):
            journalpub_factory(authors=[author], tags=[tagged], title=f"Paper {i}")

        r = client.get("/item/show/all-tags/")
        assert r.status_code == 200
        body = r.content.decode("utf-8")
        # Count superscript element shows up with the right number for
        # the tag we just tagged 3 items with.
        assert 'class="lit-tag-cloud__count">3</sup>' in body


@pytest.mark.django_db
class TestPageHitTracking:
    """Closes umbrella #48 → Theme E (#18 + #16). Every public landing
    page now writes a PageHit; tag/author/year/journal pages capture the
    slug in ``extra_info`` so analytics can group cleanly.

    Item-detail tracking (``view_item`` calling ``create_hit(request,
    the_item.pk)``) was already in place from Phase 4 and is not retested
    here — see TestItemDetail."""

    def test_front_page_records_hit(self, client):
        from pagehit.models import PageHit

        r = client.get("/")
        assert r.status_code == 200
        assert PageHit.objects.filter(item="lit-main-page").count() == 1

    def test_about_page_records_hit(self, client):
        from pagehit.models import PageHit

        r = client.get("/about")
        assert r.status_code == 200
        assert PageHit.objects.filter(item="lit-about-page").count() == 1

    def test_show_all_items_records_hit(self, client, journalpub_factory, author):
        from pagehit.models import PageHit

        journalpub_factory(authors=[author])
        r = client.get("/item/show-all")
        assert r.status_code == 200
        assert PageHit.objects.filter(item="lit-show-all-items").count() == 1

    def test_show_all_tags_records_hit(self, client, tag):
        from pagehit.models import PageHit

        r = client.get("/item/show/all-tags/")
        assert r.status_code == 200
        assert PageHit.objects.filter(item="lit-show-all-tags").count() == 1

    def test_tag_page_records_hit_with_slug(self, client, journalpub_factory, author, tag):
        from pagehit.models import PageHit

        journalpub_factory(authors=[author], tags=[tag])
        r = client.get(f"/item/tag/{tag.slug}/")
        assert r.status_code == 200
        rows = PageHit.objects.filter(item="lit-tag-page")
        assert rows.count() == 1
        assert rows.first().extra_info == tag.slug

    def test_author_page_records_hit_with_slug(self, client, journalpub_factory, author):
        from pagehit.models import PageHit

        journalpub_factory(authors=[author])
        r = client.get(f"/item/author/{author.slug}/")
        assert r.status_code == 200
        rows = PageHit.objects.filter(item="lit-author-page")
        assert rows.count() == 1
        assert rows.first().extra_info == author.slug

    def test_year_page_records_hit_with_year(self, client, journalpub_factory, author):
        from pagehit.models import PageHit

        journalpub_factory(authors=[author], year=2024)
        r = client.get("/item/pub-by-year/2024/")
        assert r.status_code == 200
        rows = PageHit.objects.filter(item="lit-year-page")
        assert rows.count() == 1
        assert rows.first().extra_info == "2024"

    def test_journal_page_records_hit_with_slug(self, client, journalpub_factory, author):
        from pagehit.models import PageHit

        # ``journal`` fixture is auto-injected via journalpub_factory.
        pub = journalpub_factory(authors=[author])
        r = client.get(f"/item/journal/{pub.journal.slug}/")
        assert r.status_code == 200
        rows = PageHit.objects.filter(item="lit-journal-page")
        assert rows.count() == 1
        assert rows.first().extra_info == pub.journal.slug

    def test_paginated_request_does_not_double_count(self, client, journalpub_factory, author, tag):
        """Mirror of pages.search's existing skip — clicking page 2 of a
        landing page is the same visit, not a new one."""
        from pagehit.models import PageHit

        journalpub_factory(authors=[author], tags=[tag])
        client.get(f"/item/tag/{tag.slug}/")  # initial visit
        client.get(f"/item/tag/{tag.slug}/?page=2")  # paginated click
        assert PageHit.objects.filter(item="lit-tag-page").count() == 1

    def test_unknown_author_404_does_not_record_hit(self, client):
        """The view returns 404 before reaching the create_hit call when
        the slug doesn't resolve, so no PageHit row should be written."""
        from pagehit.models import PageHit

        r = client.get("/item/author/nobody/")
        assert r.status_code == 404
        assert PageHit.objects.filter(item="lit-author-page").count() == 0
