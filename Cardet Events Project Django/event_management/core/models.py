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

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    event_name = models.CharField(max_length=255)
    event_date = models.DateField()
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    description = RichTextField()
    tickets = models.BooleanField(default=False)
    signatures = models.BooleanField(default=False)
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


class Participant(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True, null=True)
    pdf_ticket = models.FileField(upload_to=pdf_ticket_path, blank=True, null=True)
    qr_code = models.ImageField(upload_to=qr_code_path, blank=True, null=True)
    registered_at = models.DateTimeField(auto_now_add=True)

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


class Attendance(models.Model):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    present = models.BooleanField(default=False)
    signature_file = models.FileField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.participant.name} - {'Present' if self.present else 'Absent'} - {self.event.event_name}"


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
