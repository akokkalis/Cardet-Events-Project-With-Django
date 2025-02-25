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
)


class EventAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.TextField: {"widget": CKEditorWidget()},
    }
    list_display = ("event_name", "event_date", "status")
    list_filter = ("status", "event_date")
    search_fields = ("event_name", "location")


class AttendanceAdmin(admin.ModelAdmin):

    list_display = ("event", "present", "signature_file", "timestamp")
    list_filter = ("event", "present", "signature_file", "timestamp")
    search_fields = ("event_name", "location")


admin.site.register(Company)
admin.site.register(Staff)
admin.site.register(Event, EventAdmin)
admin.site.register(Participant)
admin.site.register(Attendance, AttendanceAdmin)
admin.site.register(EmailConfiguration)


@admin.register(Status)
class StatusAdmin(admin.ModelAdmin):
    list_display = ("name", "color")
    search_fields = ("name",)
