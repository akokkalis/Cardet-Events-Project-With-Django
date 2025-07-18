from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
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
    RSVPResponse,
    RSVPEmailLog,
    CertificateGenerationLog,
    CSVImportLog,
    TicketType,
    Order,
    OrderItem,
    Payment,
    PaidTicket,
)


class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 0  # Don't show extra empty forms
    readonly_fields = (
        "registered_at",
        "approval_status_display",
        "pdf_ticket_link",
        "qr_code_display",
    )
    fields = (
        "name",
        "email",
        "phone",
        "approval_status_display",
        "pdf_ticket_link",
        "qr_code_display",
        "registered_at",
    )

    def approval_status_display(self, obj):
        """Display approval status with color coding"""
        if obj.approval_status == "approved":
            return format_html(
                '<span style="color: green; font-weight: bold;">✅ Approved</span>'
            )
        elif obj.approval_status == "rejected":
            return format_html(
                '<span style="color: red; font-weight: bold;">❌ Rejected</span>'
            )
        else:
            return format_html(
                '<span style="color: orange; font-weight: bold;">⏳ Pending</span>'
            )

    approval_status_display.short_description = "Status"

    def pdf_ticket_link(self, obj):
        """Display PDF ticket download link if available"""
        if obj.pdf_ticket:
            return format_html(
                '<a href="{}" target="_blank">📄 Download PDF</a>', obj.pdf_ticket.url
            )
        return format_html('<span style="color: gray;">No PDF</span>')

    pdf_ticket_link.short_description = "PDF Ticket"

    def qr_code_display(self, obj):
        """Display QR code thumbnail if available"""
        if obj.qr_code:
            return format_html(
                '<img src="{}" width="30" height="30" title="QR Code" />',
                obj.qr_code.url,
            )
        return format_html('<span style="color: gray;">No QR</span>')

    qr_code_display.short_description = "QR Code"

    def has_add_permission(self, request, obj=None):
        return False  # Disable adding participants through admin (use registration form instead)


class EventAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.TextField: {"widget": CKEditorWidget()},
    }
    list_display = [
        "event_name",
        "company",
        "event_date",
        "start_time",
        "end_time",
        "location",
        "status",
        "tickets",
        "paid_tickets",
        "has_registration_limit",
        "registration_limit",
        "public_registration_enabled",
        "auto_approval_enabled",
    ]
    list_filter = [
        "company",
        "event_date",
        "status",
        "tickets",
        "paid_tickets",
        "has_registration_limit",
        "public_registration_enabled",
        "auto_approval_enabled",
    ]
    search_fields = ["event_name", "company__name", "location"]
    date_hierarchy = "event_date"
    inlines = [ParticipantInline]
    readonly_fields = ["uuid"]
    fieldsets = (
        (
            "Event Information",
            {
                "fields": (
                    "uuid",
                    "company",
                    "event_name",
                    "event_date",
                    "start_time",
                    "end_time",
                    "location",
                    "description",
                    "status",
                )
            },
        ),
        (
            "Registration Settings",
            {
                "fields": (
                    "tickets",
                    "has_registration_limit",
                    "registration_limit",
                    "public_registration_enabled",
                    "auto_approval_enabled",
                    "signatures",
                )
            },
        ),
        (
            "Media",
            {
                "fields": ("image", "certificate"),
            },
        ),
    )

    def participant_count(self, obj):
        """Show participant count in the event list"""
        count = obj.participant_set.count()
        approved = obj.participant_set.filter(approval_status="approved").count()
        pending = obj.participant_set.filter(approval_status="pending").count()
        rejected = obj.participant_set.filter(approval_status="rejected").count()

        return format_html(
            "<strong>{}</strong> total<br/>"
            '<span style="color: green;">✅ {}</span> | '
            '<span style="color: orange;">⏳ {}</span> | '
            '<span style="color: red;">❌ {}</span>',
            count,
            approved,
            pending,
            rejected,
        )

    participant_count.short_description = "Participants"


class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("event", "participant", "present", "signature_file", "timestamp")
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


class ParticipantAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "email",
        "event",
        "approval_status_display",
        "registered_at",
        "pdf_ticket_status",
        "qr_code_status",
    )
    list_filter = ("approval_status", "event", "registered_at")
    search_fields = ("name", "email", "event__event_name")
    readonly_fields = ("registered_at", "pdf_ticket_link", "qr_code_display")

    def approval_status_display(self, obj):
        """Display approval status with color coding"""
        if obj.approval_status == "approved":
            return format_html(
                '<span style="color: green; font-weight: bold;">✅ Approved</span>'
            )
        elif obj.approval_status == "rejected":
            return format_html(
                '<span style="color: red; font-weight: bold;">❌ Rejected</span>'
            )
        else:
            return format_html(
                '<span style="color: orange; font-weight: bold;">⏳ Pending</span>'
            )

    approval_status_display.short_description = "Status"

    def pdf_ticket_status(self, obj):
        """Show if PDF ticket exists"""
        if obj.pdf_ticket:
            return format_html('<span style="color: green;">✅ Generated</span>')
        return format_html('<span style="color: gray;">❌ Not Generated</span>')

    pdf_ticket_status.short_description = "PDF Ticket"

    def qr_code_status(self, obj):
        """Show if QR code exists"""
        if obj.qr_code:
            return format_html('<span style="color: green;">✅ Generated</span>')
        return format_html('<span style="color: gray;">❌ Not Generated</span>')

    qr_code_status.short_description = "QR Code"

    def pdf_ticket_link(self, obj):
        """Display PDF ticket download link if available"""
        if obj.pdf_ticket:
            return format_html(
                '<a href="{}" target="_blank">📄 Download PDF Ticket</a>',
                obj.pdf_ticket.url,
            )
        return format_html('<span style="color: gray;">No PDF ticket generated</span>')

    pdf_ticket_link.short_description = "PDF Ticket Download"

    def qr_code_display(self, obj):
        """Display QR code image if available"""
        if obj.qr_code:
            return format_html(
                '<img src="{}" width="100" height="100" title="QR Code for {}" />',
                obj.qr_code.url,
                obj.name,
            )
        return format_html('<span style="color: gray;">No QR code generated</span>')

    qr_code_display.short_description = "QR Code"

    fieldsets = (
        ("Participant Information", {"fields": ("event", "name", "email", "phone")}),
        ("Registration Status", {"fields": ("approval_status", "registered_at")}),
        (
            "Generated Files",
            {
                "fields": ("pdf_ticket_link", "qr_code_display"),
                "classes": ("collapse",),
            },
        ),
        (
            "Custom Data",
            {
                "fields": ("submitted_data",),
                "classes": ("collapse",),
                "description": "JSON data submitted through custom fields",
            },
        ),
    )


admin.site.register(Company)
admin.site.register(Staff)
admin.site.register(Event, EventAdmin)
admin.site.register(Participant, ParticipantAdmin)
admin.site.register(Attendance, AttendanceAdmin)
admin.site.register(EmailConfiguration)
admin.site.register(EventCustomField, EventCustomFieldAdmin)
admin.site.register(EventEmail, EventEmailAdmin)


class RSVPResponseAdmin(admin.ModelAdmin):
    list_display = ("participant", "event", "response_display", "response_date")
    list_filter = ("response", "event", "response_date")
    search_fields = ("participant__name", "participant__email", "event__event_name")
    readonly_fields = ("response_date",)
    ordering = ("-response_date",)

    def response_display(self, obj):
        """Display RSVP response with color coding"""
        if obj.response == "attend":
            return format_html(
                '<span style="color: green; font-weight: bold;">✅ Attend</span>'
            )
        elif obj.response == "cant_make_it":
            return format_html(
                '<span style="color: red; font-weight: bold;">❌ Can\'t make it</span>'
            )
        else:  # maybe
            return format_html(
                '<span style="color: orange; font-weight: bold;">❓ Maybe</span>'
            )

    response_display.short_description = "Response"


admin.site.register(RSVPResponse, RSVPResponseAdmin)


class RSVPEmailLogAdmin(admin.ModelAdmin):
    list_display = (
        "event",
        "user",
        "status_display",
        "email_stats",
        "started_at",
        "completed_at",
    )
    list_filter = ("status", "event", "started_at")
    search_fields = ("event__event_name", "user__username")
    readonly_fields = ("started_at", "completed_at", "progress_percentage")
    ordering = ("-started_at",)

    def status_display(self, obj):
        """Display status with color coding"""
        if obj.status == "completed":
            return format_html(
                '<span style="color: green; font-weight: bold;">✅ Completed</span>'
            )
        elif obj.status == "failed":
            return format_html(
                '<span style="color: red; font-weight: bold;">❌ Failed</span>'
            )
        else:  # in_progress
            return format_html(
                '<span style="color: orange; font-weight: bold;">⏳ In Progress</span>'
            )

    status_display.short_description = "Status"

    def email_stats(self, obj):
        """Display email sending statistics"""
        return format_html(
            "📧 {}/{} sent<br/>" "❌ {} failed",
            obj.emails_sent,
            obj.total_recipients,
            obj.emails_failed,
        )

    email_stats.short_description = "Email Stats"

    fieldsets = (
        (None, {"fields": ("event", "user", "status")}),
        (
            "Email Information",
            {
                "fields": (
                    "total_recipients",
                    "emails_sent",
                    "emails_failed",
                    "progress_percentage",
                )
            },
        ),
        (
            "Timing",
            {
                "fields": ("started_at", "completed_at"),
            },
        ),
        (
            "Log Messages",
            {
                "fields": ("log_messages",),
                "description": "Detailed log of email sending process (success and error messages)",
            },
        ),
    )


admin.site.register(RSVPEmailLog, RSVPEmailLogAdmin)


class CertificateGenerationLogAdmin(admin.ModelAdmin):
    list_display = (
        "event",
        "user",
        "status_display",
        "certificate_stats",
        "progress_display",
        "started_at",
        "completed_at",
    )
    list_filter = ("status", "event", "started_at")
    search_fields = ("event__event_name", "user__username")
    readonly_fields = ("started_at", "completed_at", "progress_percentage")
    ordering = ("-started_at",)

    def status_display(self, obj):
        """Display status with color coding"""
        if obj.status == "completed":
            return format_html(
                '<span style="color: green; font-weight: bold;">✅ Completed</span>'
            )
        elif obj.status == "failed":
            return format_html(
                '<span style="color: red; font-weight: bold;">❌ Failed</span>'
            )
        else:
            return format_html(
                '<span style="color: orange; font-weight: bold;">⏳ In Progress</span>'
            )

    status_display.short_description = "Status"

    def certificate_stats(self, obj):
        """Display certificate generation statistics"""
        return format_html(
            "✅ Generated: <strong>{}</strong> | ❌ Failed: <strong>{}</strong> | 📊 Total: <strong>{}</strong>",
            obj.successful_generations,
            obj.failed_generations,
            obj.total_participants,
        )

    certificate_stats.short_description = "Certificate Statistics"

    def progress_display(self, obj):
        """Display progress with percentage"""
        if obj.status == "completed":
            return format_html(
                '<span style="color: green; font-weight: bold;">100% Complete</span>'
            )
        elif obj.status == "failed":
            return format_html(
                '<span style="color: red; font-weight: bold;">Failed</span>'
            )
        else:
            return format_html(
                '<span style="color: blue; font-weight: bold;">{}%</span>',
                obj.progress_percentage,
            )

    progress_display.short_description = "Progress"

    fieldsets = (
        (None, {"fields": ("event", "user", "status")}),
        (
            "Progress Information",
            {
                "fields": (
                    "total_participants",
                    "processed_participants",
                    "successful_generations",
                    "failed_generations",
                    "progress_percentage",
                )
            },
        ),
        (
            "Timing",
            {
                "fields": ("started_at", "completed_at"),
            },
        ),
        (
            "Log Messages",
            {
                "fields": ("log_messages",),
                "description": "Detailed log of certificate generation process (success and error messages)",
            },
        ),
    )


admin.site.register(CertificateGenerationLog, CertificateGenerationLogAdmin)


class CSVImportLogAdmin(admin.ModelAdmin):
    list_display = (
        "event",
        "user",
        "status_display",
        "import_stats",
        "started_at",
        "completed_at",
    )
    list_filter = ("status", "event", "started_at")
    search_fields = ("event__event_name", "user__username")
    readonly_fields = ("started_at", "completed_at", "progress_percentage")
    ordering = ("-started_at",)

    def status_display(self, obj):
        """Display status with color coding"""
        if obj.status == "completed":
            return format_html(
                '<span style="color: green; font-weight: bold;">✅ Completed</span>'
            )
        elif obj.status == "failed":
            return format_html(
                '<span style="color: red; font-weight: bold;">❌ Failed</span>'
            )
        else:  # in_progress
            return format_html(
                '<span style="color: orange; font-weight: bold;">⏳ In Progress</span>'
            )

    status_display.short_description = "Status"

    def import_stats(self, obj):
        """Display import statistics"""
        return format_html(
            "✅ {}/{} imported<br/>" "❌ {} failed",
            obj.successful_imports,
            obj.total_rows,
            obj.failed_imports,
        )

    import_stats.short_description = "Import Stats"

    fieldsets = (
        (None, {"fields": ("event", "user", "status")}),
        (
            "Import Information",
            {
                "fields": (
                    "total_rows",
                    "processed_rows",
                    "successful_imports",
                    "failed_imports",
                    "progress_percentage",
                )
            },
        ),
        (
            "Timing",
            {
                "fields": ("started_at", "completed_at"),
            },
        ),
        (
            "Log Messages",
            {
                "fields": ("log_messages",),
                "description": "Detailed log of import process (success and error messages)",
            },
        ),
    )


admin.site.register(CSVImportLog, CSVImportLogAdmin)


@admin.register(Status)
class StatusAdmin(admin.ModelAdmin):
    list_display = ("name", "color")
    search_fields = ("name",)


# Ticketing System Admin


class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 1
    fields = ("name", "description", "price", "max_quantity", "is_active")


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "event",
        "price",
        "max_quantity",
        "tickets_sold",
        "tickets_available",
        "is_active",
    )
    list_filter = ("is_active", "event__company", "event")
    search_fields = ("name", "event__event_name")
    readonly_fields = ("tickets_sold", "tickets_available", "created_at", "updated_at")

    def tickets_sold(self, obj):
        return obj.tickets_sold

    tickets_sold.short_description = "Sold"

    def tickets_available(self, obj):
        return obj.tickets_available

    tickets_available.short_description = "Available"


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("total_price",)
    fields = ("ticket_type", "quantity", "price_per_ticket", "total_price")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "participant",
        "event",
        "total_amount",
        "payment_status",
        "created_at",
    )
    list_filter = ("payment_status", "event__company", "event", "created_at")
    search_fields = (
        "order_number",
        "participant__name",
        "participant__email",
        "event__event_name",
    )
    readonly_fields = ("order_number", "total_quantity", "created_at", "updated_at")
    inlines = [OrderItemInline]

    def total_quantity(self, obj):
        return obj.total_quantity

    total_quantity.short_description = "Total Tickets"


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "ticket_type",
        "quantity",
        "price_per_ticket",
        "total_price",
    )
    list_filter = ("ticket_type__event__company", "ticket_type__event", "ticket_type")
    search_fields = ("order__order_number", "ticket_type__name")
    readonly_fields = ("total_price",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "payment_method",
        "payment_status",
        "amount_paid",
        "payment_date",
        "created_at",
    )
    list_filter = ("payment_method", "payment_status", "created_at")
    search_fields = (
        "order__order_number",
        "stripe_payment_intent_id",
        "stripe_charge_id",
    )
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            "Order Information",
            {
                "fields": (
                    "order",
                    "payment_method",
                    "payment_status",
                    "amount_paid",
                    "transaction_fee",
                )
            },
        ),
        (
            "Stripe Information",
            {"fields": ("stripe_payment_intent_id", "stripe_charge_id")},
        ),
        ("Payment Details", {"fields": ("payment_date", "failure_reason")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


class PaidTicketAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "ticket_type",
        "participant",
        "uuid",
        "scanned",
        "created_at",
    )
    search_fields = (
        "order__order_number",
        "participant__name",
        "participant__email",
        "ticket_type__name",
        "uuid",
    )
    list_filter = ("order__event", "ticket_type", "scanned", "created_at")
    readonly_fields = ("uuid", "created_at")


admin.site.register(PaidTicket, PaidTicketAdmin)
