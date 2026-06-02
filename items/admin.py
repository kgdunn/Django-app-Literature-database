from django.contrib import admin

from items.models import (
    Author,
    AuthorGroup,
    Book,
    ConferenceProceeding,
    InCollection,
    Item,
    Journal,
    JournalPub,
    Publisher,
    School,
    Thesis,
)


class AuthorGroupInline(admin.TabularInline):
    model = AuthorGroup
    extra = 1


class AuthorAdmin(admin.ModelAdmin):
    list_display = (
        "last_name",
        "first_name",
        "middle_initials",
    )
    list_display_links = ("last_name",)
    ordering = ["last_name"]


class ItemAdmin(admin.ModelAdmin):
    inlines = (AuthorGroupInline,)
    # `pdf_file` stays in list_display so admins can confirm at a glance
    # which items have a PDF attached for FTS extraction. By default the
    # file is not exposed publicly; `pdf_is_public` (default off) is the
    # per-item override that surfaces it via the `view_pdf` view, so it's
    # shown in the list + offered as a filter to make the public ones easy
    # to audit.
    list_display = (
        "id",
        "title",
        "author_list",
        "year",
        "pdf_file",
        "pdf_is_public",
        "doi_link",
        "item_type",
        "date_created",
        "has_extra",
    )
    list_display_links = ("title",)
    list_filter = ("pdf_is_public",)
    ordering = ["-id"]
    # `authors` is managed via the inline above; Django 2+ refuses to put a
    # M2M with a `through=` model in filter_horizontal (admin.E013).
    filter_horizontal = ["tags"]


class JournalPubAdmin(admin.ModelAdmin):
    inlines = (AuthorGroupInline,)
    list_display = (
        "title",
        "author_list",
        "year",
        "doi_link",
        "journal",
        "volume",
        "page_start",
        "page_end",
    )
    list_display_links = ("title",)
    ordering = ["-date_created"]
    filter_horizontal = ["tags"]


class ThesisAdmin(admin.ModelAdmin):
    inlines = (AuthorGroupInline,)
    list_display = ("author_list", "title", "thesis_type", "year", "school")
    list_display_links = ("title",)
    ordering = ["-date_created"]
    filter_horizontal = ["supervisors", "tags"]


class BookAdmin(admin.ModelAdmin):
    inlines = (AuthorGroupInline,)
    list_display = (
        "author_list",
        "title",
        "year",
        "isbn",
        "publisher",
    )
    list_display_links = ("title",)
    ordering = ["-date_created"]
    filter_horizontal = ["editors", "tags"]


class JournalAdmin(admin.ModelAdmin):
    """Sorted alphabetical list + a search box (issue #23) so admins can
    spot duplicates ("Analytica Chimica Acta" vs. variants) at a glance
    before merging them. The case-insensitive UniqueConstraint added in
    migration 0007 prevents *new* duplicates from being created."""

    list_display = ("name", "website")
    ordering = ["name"]
    search_fields = ("name",)
    list_per_page = 100


admin.site.register(Author, AuthorAdmin)
admin.site.register(Journal, JournalAdmin)
admin.site.register(Publisher)
admin.site.register(School)


class InCollectionAdmin(admin.ModelAdmin):
    inlines = (AuthorGroupInline,)
    list_display = (
        "author_list",
        "title",
        "book_title",
        "year",
        "publisher",
    )
    list_display_links = ("title",)
    ordering = ["-date_created"]
    filter_horizontal = ["editors", "tags"]


admin.site.register(Item, ItemAdmin)
admin.site.register(JournalPub, JournalPubAdmin)
admin.site.register(Book, BookAdmin)
admin.site.register(ConferenceProceeding)
admin.site.register(Thesis, ThesisAdmin)
admin.site.register(InCollection, InCollectionAdmin)
