from django.urls import re_path

from pages.views import about_page, front_page, search

urlpatterns = [
    # Front page
    re_path(r'^$', front_page, name='lit-main-page'),

    # About page
    re_path(r'about', about_page, name='lit-about-page'),

    # Search view (route name preserved as `haystack_search` so existing
    # `{% url 'haystack_search' %}` template references keep working;
    # Phase 3 replaces the body with Postgres-FTS).
    re_path(r'search', search, name='haystack_search'),
]
