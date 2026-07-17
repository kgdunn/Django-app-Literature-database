from django.urls import re_path

from pages.views import about_page, front_page, healthz, robots_txt, search

urlpatterns = [
    # Front page
    re_path(r"^$", front_page, name="lit-main-page"),
    # About page
    re_path(r"about", about_page, name="lit-about-page"),
    # Site-wide search (Postgres FTS, both dev and prod).
    re_path(r"search", search, name="search"),
    # Liveness probe (Dockerfile HEALTHCHECK + Phase-9 deploy script).
    re_path(r"^healthz/?$", healthz, name="healthz"),
    # Issue #72: keep /admin/ etc. out of search-engine indexes.
    re_path(r"^robots\.txt$", robots_txt, name="lit-robots-txt"),
]
