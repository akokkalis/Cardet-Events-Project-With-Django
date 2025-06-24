from django.contrib import admin
from .models import Event
from ckeditor.widgets import CKEditorWidget
from django.db import models

# Register your models here.

from .models import (
    Company,
    Staff,
    Event,
    Participant,
    Attendance,
    Status,
    EmailConfiguration,
    EventCustomField,
    EventEmail,
)


class EventAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.TextField: {"widget": CKEditorWidget()},
    }
    list_display = ("event_name", "event_date", "status", "uuid")
    list_filter = ("status", "event_date")
    search_fields = ("event_name", "location")


class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("event", "present", "signature_file", "timestamp")
    list_filter = ("event", "present", "signature_file", "timestamp")
    search_fields = ("event_name", "location")


class EventCustomFieldAdmin(admin.ModelAdmin):
    list_display = ("label", "event", "field_type", "required", "order", "help_text")
    list_filter = ("event", "field_type", "required")
    search_fields = ("label", "event__event_name")
    ordering = ("event", "order")


class EventEmailAdmin(admin.ModelAdmin):
    list_display = ("event", "reason", "subject")
    list_filter = ("reason", "event__event_date", "event__status")
    search_fields = ("event__event_name", "subject", "body")
    ordering = ("event", "reason")

    fieldsets = (
        (None, {"fields": ("event", "reason", "subject")}),
        (
            "Email Template",
            {
                "fields": ("body",),
                "description": "Available placeholders: {{ name }}, {{ event_name }}, {{ event_date }}, {{ event_location }}, {{ start_time }}, {{ end_time }}",
            },
        ),
    )

    # Customize the body field to use a larger textarea
    formfield_overrides = {
        models.TextField: {
            "widget": admin.widgets.AdminTextareaWidget(attrs={"rows": 10, "cols": 80})
        },
    }


admin.site.register(Company)
admin.site.register(Staff)
admin.site.register(Event, EventAdmin)
admin.site.register(Participant)
admin.site.register(Attendance, AttendanceAdmin)
admin.site.register(EmailConfiguration)
admin.site.register(EventCustomField, EventCustomFieldAdmin)
admin.site.register(EventEmail, EventEmailAdmin)


@admin.register(Status)
class StatusAdmin(admin.ModelAdmin):
    list_display = ("name", "color")
    search_fields = ("name",)
