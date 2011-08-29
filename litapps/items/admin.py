from django.contrib import admin
from django import forms
from models import (Author, AuthorGroup, Journal, Publisher, Item, School,
                     JournalPub, Book, ConferenceProceeding, Thesis)


class AuthorGroupInline(admin.TabularInline):
    model = AuthorGroup
    extra = 1

class AuthorAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'middle_initials',)
    list_display_links = ('last_name', )
    ordering = ['last_name']


class ItemAdmin(admin.ModelAdmin):
    inlines = (AuthorGroupInline,)
    list_display = ('title', 'year', 'author_list', 'doi_link',
                    'date_created', 'item_type')
    list_display_links = ('title', )
    ordering = ['-date_created']
    filter_horizontal = ['authors', 'tags']


class JournalPubAdmin(admin.ModelAdmin):
    inlines = (AuthorGroupInline,)
    list_display = ('title', 'author_list', 'year', 'doi_link', 'journal',
                    'volume', 'page_start', 'page_end', )
    list_display_links = ('title', )
    ordering = ['-date_created']
    filter_horizontal = ['authors', 'tags']


class ThesisAdmin(admin.ModelAdmin):
    inlines = (AuthorGroupInline,)
    list_display = ('author_list', 'title', 'year', 'school')
    list_display_links = ('title', )
    ordering = ['-date_created']
    filter_horizontal = ['authors', 'supervisors', 'tags']


class BookAdmin(admin.ModelAdmin):
    inlines = (AuthorGroupInline,)
    list_display = ('author_list', 'title', 'year', 'isbn', 'publisher',)
    list_display_links = ('title', )
    ordering = ['-date_created']
    filter_horizontal = ['authors', 'editors', 'tags']


admin.site.register(Author, AuthorAdmin)
admin.site.register(Journal)
admin.site.register(Publisher)
admin.site.register(School)

admin.site.register(Item, ItemAdmin)
admin.site.register(JournalPub, JournalPubAdmin)
admin.site.register(Book, BookAdmin)
admin.site.register(ConferenceProceeding)
admin.site.register(Thesis, ThesisAdmin)
