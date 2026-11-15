from django.contrib import admin

from .models import Pin, Board, SiteSettings


class PinAdmin(admin.ModelAdmin):
    pass


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """Singleton admin: there is exactly one settings row."""

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # jump straight to the single settings object
        from django.shortcuts import redirect
        from django.urls import reverse
        obj = SiteSettings.load()
        return redirect(reverse("admin:core_sitesettings_change", args=(obj.pk,)))


admin.site.register(Pin, PinAdmin)
admin.site.register(Board)
