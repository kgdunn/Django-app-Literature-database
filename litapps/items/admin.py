from django.contrib import admin
from models import (Author, Journal, Publisher, Item, School,
                     JournalPub, Book, ConferenceProceeding, Thesis)

class ItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'year', 'doi_link', 'date_created', 'item_type')
    list_display_links = ('title', )
    ordering = ['-date_created']

class JournalPubAdmin(admin.ModelAdmin):
    list_display = ('title', 'year', 'doi_link', 'journal', 'volume',
                    'page_start', 'page_end')
    list_display_links = ('title', )
    ordering = ['-date_created']

class ThesisAdmin(admin.ModelAdmin):
    list_display = ('title', 'year', 'school', )
    list_display_links = ('title', )
    ordering = ['-date_created']


admin.site.register(Author)
admin.site.register(Journal)
admin.site.register(Publisher)
admin.site.register(School)

admin.site.register(Item, ItemAdmin)
admin.site.register(JournalPub, JournalPubAdmin)
admin.site.register(Book)
admin.site.register(ConferenceProceeding)
admin.site.register(Thesis, ThesisAdmin)
