from django.contrib import admin

from pagehit.models import PageHit


@admin.register(PageHit)
class PageHitAdmin(admin.ModelAdmin):
    """The PageHit table is an append-only audit log: rows shouldn't be
    edited or deleted from the admin. Phase 4 dropped the PII columns
    (`ua_string`, `ip_address`); what's left is intentionally minimal.
    """

    list_display = ("datetime", "item", "item_pk", "extra_info")
    list_filter = ("item",)
    date_hierarchy = "datetime"
    search_fields = ("item", "extra_info")
    readonly_fields = ("datetime", "item", "item_pk", "extra_info")
    list_per_page = 200

    def has_add_permission(self, request):
        # PageHit rows are written only by `pagehit.views.create_hit`, never
        # by hand from the admin.
        return False
