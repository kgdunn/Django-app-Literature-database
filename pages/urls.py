from django.urls import re_path

from pages.views import about_page, front_page, search

urlpatterns = [
    # Front page
    re_path(r'^$', front_page, name='lit-main-page'),

    # About page
    re_path(r'about', about_page, name='lit-about-page'),

    # Site-wide search (Postgres FTS in prod, icontains fallback in SQLite dev).
    re_path(r'search', search, name='search'),
]
