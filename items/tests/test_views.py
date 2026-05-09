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

    def test_healthz_returns_200_with_no_store(self, client):
        for path in ("/healthz", "/healthz/"):
            r = client.get(path)
            assert r.status_code == 200, path
            assert r.content == b"ok"
            assert r["Cache-Control"] == "no-store"


@pytest.mark.django_db
class TestSecurityHeaders:
    def test_csp_present_on_front_page(self, client):
        r = client.get("/")
        csp = r.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp
        assert "https://cdn.jsdelivr.net" in csp
        assert "frame-ancestors 'none'" in csp

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

    def test_exact_title_ranks_above_distractors(
        self, client, journalpub_factory, author
    ):
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
            "monitoring monitoring monitoring process process diagnosis "
            "diagnosis multi block multi block. " * 30
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
            f"Target ranked below distractors: target at {target_pos}, "
            f"first distractor at {first_distractor_pos}"
        )
        assert target.title.encode() in r.content


@pytest.mark.django_db
class TestNoPdfDownloadEndpoint:
    """Phase 5 hard rule: no public PDF download URL exists."""

    def test_lit_download_pdf_url_name_does_not_resolve(self):
        with pytest.raises(NoReverseMatch):
            reverse("lit-download-pdf", args=[1])

    def test_legacy_download_pdf_path_redirects_to_canonical(
        self, client, journalpub_factory, author
    ):
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

    def test_tag_filter(self, client, journalpub_factory, author, tag):
        journalpub_factory(authors=[author], tags=[tag], title="Has Fourier tag")
        journalpub_factory(authors=[author], title="No tag")
        r = client.get(f"/item/tag/{tag.slug}/")
        assert r.status_code == 200
        assert b"Has Fourier tag" in r.content
        assert b"No tag" not in r.content


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

    def test_tag_page_records_hit_with_slug(
        self, client, journalpub_factory, author, tag
    ):
        from pagehit.models import PageHit

        journalpub_factory(authors=[author], tags=[tag])
        r = client.get(f"/item/tag/{tag.slug}/")
        assert r.status_code == 200
        rows = PageHit.objects.filter(item="lit-tag-page")
        assert rows.count() == 1
        assert rows.first().extra_info == tag.slug

    def test_author_page_records_hit_with_slug(
        self, client, journalpub_factory, author
    ):
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

    def test_journal_page_records_hit_with_slug(
        self, client, journalpub_factory, author
    ):
        from pagehit.models import PageHit

        # ``journal`` fixture is auto-injected via journalpub_factory.
        pub = journalpub_factory(authors=[author])
        r = client.get(f"/item/journal/{pub.journal.slug}/")
        assert r.status_code == 200
        rows = PageHit.objects.filter(item="lit-journal-page")
        assert rows.count() == 1
        assert rows.first().extra_info == pub.journal.slug

    def test_paginated_request_does_not_double_count(
        self, client, journalpub_factory, author, tag
    ):
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
