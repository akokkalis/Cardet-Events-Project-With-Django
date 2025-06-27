from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
import os
from ckeditor.fields import RichTextField
from django.core.files.base import ContentFile
import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

COMPANY_MASTER_FOLDER = os.path.join(settings.MEDIA_ROOT, "Companies")
EVENTS_MASTER_FOLDER = os.path.join(
    settings.MEDIA_ROOT, "Events"
)  # Master "Events" directory


def company_logo_path(instance, filename):
    """Dynamically generate the upload path for company logos."""
    if instance.id:  # Ensure instance has an ID before using it
        company_folder = f"Companies/{instance.id}_{instance.name}/"
        return os.path.join(
            company_folder, filename
        )  # Keep the original filename and extension
    return f"temp/{filename}"  # Temporary storage before ID is assigned


def event_image_path(instance, filename):
    """Returns the path to store event images inside the event folder."""

    if instance.id:  # Ensure the instance has an ID before using it
        return os.path.join(
            f"Events/{instance.id}_{instance.event_name.replace(' ', '_')}",
            "event_image",
            filename,
        )
    return f"temp/{filename}"  # Temporary storage before ID is assigned


def pdf_ticket_path(instance, filename):
    sanitized_email = instance.email.replace("@", "_").replace(".", "_")
    print("SANITIZED EMAIL")
    print(sanitized_email)
    print()
    pdf_filename = f"{instance.name}_{sanitized_email}_ticket.pdf"
    """Returns the correct path to store PDF tickets inside the event folder."""
    return f"Events/{instance.event.id}_{instance.event.event_name.replace(' ', '_')}/pdf_tickets/{pdf_filename}"


def qr_code_path(instance, filename):
    """Returns the correct path to store QR codes inside the event folder."""
    return f"Events/{instance.event.id}_{instance.event.event_name.replace(' ', '_')}/qr_codes/{instance.name}_{instance.email}_qr.png"


def custom_field_file_path(instance, filename):
    """Returns the path to store custom field files inside the event folder."""
    sanitized_email = instance.participant.email.replace("@", "_").replace(".", "_")
    sanitized_field_name = (
        instance.field_label.replace(" ", "_").replace("/", "_").replace("\\", "_")
    )
    return f"Events/{instance.participant.event.id}_{instance.participant.event.event_name.replace(' ', '_')}/custom_field_files/{sanitized_field_name}_{sanitized_email}_{filename}"


class Company(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    logo = models.ImageField(
        upload_to=company_logo_path, blank=True, null=True
    )  # New field for logo

    def __str__(self):
        return self.name


class EmailConfiguration(models.Model):
    """Stores SMTP settings for each company."""

    company = models.OneToOneField(
        "Company", on_delete=models.CASCADE, related_name="email_config"
    )
    smtp_server = models.CharField(max_length=255)
    smtp_port = models.IntegerField(
        default=587, validators=[MinValueValidator(1), MaxValueValidator(65535)]
    )
    email_address = models.EmailField()
    email_password = models.CharField(max_length=255)  # ⚠ Consider encrypting it!
    use_tls = models.BooleanField(default=True)
    use_ssl = models.BooleanField(default=False)

    def __str__(self):
        return f"Email Config for {self.company.name}"


class Staff(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE
    )  # Django’s built-in user model
    role = models.CharField(
        max_length=10, choices=[("admin", "Admin"), ("staff", "Staff")], default="staff"
    )

    def __str__(self):
        return self.user.username


class Status(models.Model):
    name = models.CharField(
        max_length=50, unique=True
    )  # Example: "Pending", "Completed", "Canceled"
    color = models.CharField(
        max_length=20, default="#000000"
    )  # Optional: HEX color for display
    priority = models.IntegerField(
        default=99,
        help_text="Lower numbers have higher priority. Completed events should have a higher number.",
    )  # Custom priority field

    def __str__(self):
        return self.name


class Event(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    event_name = models.CharField(max_length=255)
    event_date = models.DateField()
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    description = RichTextField()
    tickets = models.BooleanField(
        default=False,
        help_text="Enable this if you want to have ticketing system for the event.",
    )
    signatures = models.BooleanField(
        default=False,
        help_text="Enable this if you want to collect signatures from participants at the event.",
    )
    public_registration_enabled = models.BooleanField(
        default=False,
        help_text="Enable this if you want to allow public registration via link.",
    )
    auto_approval_enabled = models.BooleanField(
        default=True,
        help_text="Enable this if you want registrations to be automatically approved. If disabled, registrations will require manual approval.",
    )
    image = models.ImageField(upload_to=event_image_path, blank=True, null=True)
    status = models.ForeignKey(Status, on_delete=models.SET_NULL, null=True, blank=True)

    def get_event_folder(self):
        """Returns the event folder path inside 'Events/'."""
        return os.path.join(
            EVENTS_MASTER_FOLDER, f"{self.id}_{self.event_name.replace(' ','_')}"
        )

    def __str__(self):
        return (
            f"{self.event_name} ({self.event_date} {self.start_time} - {self.end_time})"
        )


class EventCustomField(models.Model):
    FIELD_TYPES = (
        ("text", "Text"),
        ("textarea", "Textarea"),
        ("number", "Number"),
        ("email", "Email"),
        ("select", "Select"),
        ("range", "Range"),
        ("checkbox", "True or False"),
        ("multiselect", "Multi-select"),
        ("date", "Date"),
        ("time", "Time"),
        ("datetime", "Date & Time"),
        ("file", "File Upload"),
    )

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="custom_fields"
    )
    label = models.CharField(max_length=255)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)
    required = models.BooleanField(default=False)
    options = models.TextField(
        blank=True,
        help_text="Comma-separated options (for 'select' and 'multiselect' types) or min,max values (for 'range' type)",
    )
    help_text = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Optional help text to guide users when filling out this field",
    )
    order = models.PositiveIntegerField(
        default=1, help_text="Display order of this field (1 = first, 2 = second, etc.)"
    )

    @property
    def options_list(self):
        """Return a list of options for select and multiselect fields."""
        if self.options:
            return [option.strip() for option in self.options.split(",")]
        return []

    @property
    def range_values(self):
        """Return min and max values for range fields as a tuple (min, max)."""
        if self.field_type == "range" and self.options:
            try:
                range_parts = [part.strip() for part in self.options.split(",")]
                if len(range_parts) == 2:
                    return int(range_parts[0]), int(range_parts[1])
            except (ValueError, IndexError):
                pass
        return 0, 100  # Default range if not specified or invalid

    class Meta:
        unique_together = ["event", "order"]
        ordering = ["order"]

    def clean(self):
        from django.core.exceptions import ValidationError

        # Check for duplicate order numbers within the same event
        # Only validate if we have both event and order (during form validation this might not be set yet)
        if hasattr(self, "event") and self.event and self.order:
            existing_field = (
                EventCustomField.objects.filter(event=self.event, order=self.order)
                .exclude(pk=self.pk)
                .first()
            )

            if existing_field:
                raise ValidationError(
                    {
                        "order": f'Order number {self.order} is already used by field "{existing_field.label}". Please choose a different order number.'
                    }
                )

    def save(self, *args, **kwargs):
        # Only run validation if the event is set (to avoid RelatedObjectDoesNotExist during form processing)
        if hasattr(self, "event") and self.event:
            self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.label} ({self.event.event_name})"


class Participant(models.Model):
    APPROVAL_CHOICES = [
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("pending", "Pending"),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True, null=True)
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_CHOICES,
        default="pending",
        help_text="Status of the participant's registration approval",
    )
    pdf_ticket = models.FileField(upload_to=pdf_ticket_path, blank=True, null=True)
    qr_code = models.ImageField(upload_to=qr_code_path, blank=True, null=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    submitted_data = models.JSONField(blank=True, null=True)

    class Meta:
        unique_together = (
            "email",
            "event",
        )  # Ensure no duplicate participants in the same event

    def __str__(self):
        return self.name

    def generate_qr_code(self):
        """Generate a QR Code linking to the participant’s check-in URL."""

        """Generate a QR Code linking to the participant’s check-in URL only if tickets are enabled."""
        if not self.event.tickets:
            print(
                f"🚫 No QR code generated: Tickets are disabled for {self.event.event_name}"
            )
            return None  # Skip QR code generation if tickets are disabled
        qr_data = f"/scan_qr/{self.event.id}/{self.id}/"
        qr = qrcode.make(qr_data)

        event_name = self.event.event_name.replace(" ", "_")

        # ✅ Ensure QR codes are saved inside the correct event folder
        qr_folder = os.path.join(
            settings.MEDIA_ROOT,
            f"Events\{self.event.id}_{self.event.event_name.replace(' ', '_')}\qr_codes",
        )

        print("QR CODE FOLDER")
        print(qr_folder)
        os.makedirs(qr_folder, exist_ok=True)

        # ✅ Fix Filename to Ensure It Matches When Saved
        sanitized_email = self.email.replace("@", "_").replace(
            ".", "_"
        )  # Replace special characters
        qr_filename = f"{self.name}_{sanitized_email}_qr.png"

        qr_path = os.path.join(qr_folder, qr_filename)

        buffer = BytesIO()
        qr.save(buffer, format="PNG")

        # ✅ Save QR code in the correct path inside the event's folder
        self.qr_code.save(
            f"Events/{self.event.id}_{self.event.event_name}/qr_codes/{qr_filename}",
            ContentFile(buffer.getvalue()),
            save=False,
        )

        return os.path.abspath(qr_path)  # ✅ Return absolute path for PDF generation


class ParticipantCustomFieldFile(models.Model):
    """Model to store files uploaded through custom fields"""

    participant = models.ForeignKey(
        Participant, on_delete=models.CASCADE, related_name="custom_field_files"
    )
    field_label = models.CharField(
        max_length=255
    )  # Store the field label for reference
    file = models.FileField(upload_to=custom_field_file_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.participant.name} - {self.field_label}"


class Attendance(models.Model):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    present = models.BooleanField(default=False)
    signature_file = models.FileField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.participant.name} - {'Present' if self.present else 'Absent'} - {self.event.event_name}"


class EventEmail(models.Model):
    REASON_CHOICES = [
        ("approval", "Approval"),
        ("rejection", "Rejection"),
        ("registration", "On Registration"),
        ("rsvp", "RSVP Request"),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="emails")
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    subject = models.CharField(max_length=255)
    body = RichTextField(
        help_text="Use placeholders like {{ name }}, {{ event_name }}, {{ event_date }}, {{ rsvp_accept_url }}, {{ rsvp_decline_url }}, {{ rsvp_maybe_url }}. HTML formatting is supported."
    )

    class Meta:
        unique_together = ("event", "reason")  # One template per reason per event
        verbose_name = "Event Email Template"
        verbose_name_plural = "Event Email Templates"

    def __str__(self):
        return f"{self.get_reason_display()} Email for {self.event.event_name}"


class RSVPResponse(models.Model):
    RESPONSE_CHOICES = [
        ("attend", "Attend"),
        ("cant_make_it", "Can't make it"),
        ("maybe", "Maybe"),
    ]

    participant = models.ForeignKey(
        Participant, on_delete=models.CASCADE, related_name="rsvp_responses"
    )
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="rsvp_responses"
    )
    response = models.CharField(max_length=12, choices=RESPONSE_CHOICES)
    response_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(
        blank=True, null=True, help_text="Optional notes from the participant"
    )

    class Meta:
        unique_together = (
            "participant",
            "event",
        )  # One RSVP response per participant per event

    def __str__(self):
        return f"{self.participant.name} - {self.get_response_display()} - {self.event.event_name}"


###  - Signal Section - ###


@receiver(post_save, sender=Company)
def create_company_folder(sender, instance, created, **kwargs):
    """Creates a folder for each company inside the 'Companies' master directory."""
    if created:  # Runs only when a new company is created
        company_folder = os.path.join(
            COMPANY_MASTER_FOLDER, f"{instance.id}_{instance.name}"
        )

        # Create the directory if it doesn't exist
        os.makedirs(company_folder, exist_ok=True)

        print(f"✅ Folder created: {company_folder}")  # Debugging info
