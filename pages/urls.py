from django.conf.urls import url, include
from pages.views import front_page, about_page, search

urlpatterns = [

    # Front page
    url(r'^$', front_page, name='lit-main-page'),

    # About page
    url(r'about', about_page, name='lit-about-page'),

    # Search views (go through our app to log search queries)
    url(r'search', search, name='haystack_search'),

]

