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
    list_display = ("label", "event", "field_type", "required", "is_email_identifier")
    list_filter = ("event", "field_type", "required", "is_email_identifier")
    search_fields = ("label", "event__event_name")


admin.site.register(Company)
admin.site.register(Staff)
admin.site.register(Event, EventAdmin)
admin.site.register(Participant)
admin.site.register(Attendance, AttendanceAdmin)
admin.site.register(EmailConfiguration)
admin.site.register(EventCustomField, EventCustomFieldAdmin)


@admin.register(Status)
class StatusAdmin(admin.ModelAdmin):
    list_display = ("name", "color")
    search_fields = ("name",)
