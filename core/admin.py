from django.contrib import admin

# Register your models here.
from .models import SiteCustomConfigs


@admin.register(SiteCustomConfigs)
class SiteCustomSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "bankrupt_status",
        "is_bankrupt",
    )
    list_editable = ("is_bankrupt",)
