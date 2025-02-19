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
    event_folder = f"Events/{instance.id}_{instance.event_name}"
    return os.path.join(event_folder, filename)


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
        return os.path.join(EVENTS_MASTER_FOLDER, f"{self.id}_{self.event_name}")

    def __str__(self):
        return (
            f"{self.event_name} ({self.event_date} {self.start_time} - {self.end_time})"
        )


class Participant(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True, null=True)
    pdf_ticket = models.FileField(upload_to="pdf_tickets/", blank=True, null=True)
    qr_code = models.ImageField(upload_to="qr_codes/", blank=True, null=True)
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
        qr_data = f"http://127.0.0.1:8000/scan_qr/{self.event.id}/{self.id}/"
        qr = qrcode.make(qr_data)

        buffer = BytesIO()
        qr.save(buffer, format="PNG")

        self.qr_code.save(
            f"{self.name}_{self.email}_qr.png",
            ContentFile(buffer.getvalue()),
            save=False,
        )


class Attendance(models.Model):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    present = models.BooleanField(default=False)
    signature_file = models.FileField(upload_to="signatures/", blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.participant.name} - {'Present' if self.present else 'Absent'}"


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
