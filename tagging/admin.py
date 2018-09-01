from django.contrib import admin
from models import Tag

class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'description',)
    list_display_links = ('name', 'slug',)


admin.site.register(Tag, TagAdmin)
