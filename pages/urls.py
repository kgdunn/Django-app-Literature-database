from django.urls import re_path

from pages.views import about_page, front_page, healthz, robots_txt, search

urlpatterns = [
    # Front page
    re_path(r"^$", front_page, name="lit-main-page"),
    # About page
    re_path(r"about", about_page, name="lit-about-page"),
    # Site-wide search. Postgres FTS (SearchVector + SearchRank) joined with
    # pg_trgm trigram similarity on author last names; same backend in dev and
    # prod (no SQLite fallback — both settings modules target Postgres).
    re_path(r"search", search, name="search"),
    # Liveness probe (Dockerfile HEALTHCHECK + Phase-9 deploy script).
    re_path(r"^healthz/?$", healthz, name="healthz"),
    # Issue #72: keep /admin/ etc. out of search-engine indexes.
    re_path(r"^robots\.txt$", robots_txt, name="lit-robots-txt"),
]
