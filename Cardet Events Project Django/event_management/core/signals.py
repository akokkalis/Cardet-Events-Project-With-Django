import os
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.conf import settings
from .models import Company, Event, Participant
import shutil
import os
from xhtml2pdf import pisa

COMPANY_MASTER_FOLDER = os.path.join(settings.MEDIA_ROOT, "Companies")


@receiver(post_save, sender=Company)
def create_company_folder(sender, instance, created, **kwargs):
    """Creates the company folder and moves the logo if necessary."""
    company_folder = os.path.join(
        COMPANY_MASTER_FOLDER, f"{instance.id}_{instance.name}"
    )

    if created:
        os.makedirs(company_folder, exist_ok=True)
        print(f"✅ Folder created: {company_folder}")

    # Move logo file from temp/ to the correct company folder
    if instance.logo and instance.logo.name.startswith("temp/"):
        old_path = os.path.join(settings.MEDIA_ROOT, instance.logo.name)
        new_path = os.path.join(company_folder, os.path.basename(instance.logo.name))

        if os.path.exists(old_path):
            shutil.move(old_path, new_path)
            instance.logo.name = os.path.relpath(new_path, settings.MEDIA_ROOT)
            instance.save(update_fields=["logo"])
            print(f"🔄 Logo moved to: {instance.logo.name}")


EVENTS_MASTER_FOLDER = os.path.join(settings.MEDIA_ROOT, "Events")


@receiver(post_save, sender=Event)
def create_event_folder(sender, instance, created, **kwargs):
    """Creates an event folder and subfolders for PDFs and Signatures when an event is added."""
    event_folder = instance.get_event_folder()
    pdf_folder = os.path.join(event_folder, "pdf_tickets")
    signatures_folder = os.path.join(event_folder, "signatures")

    if created:
        os.makedirs(event_folder, exist_ok=True)  # Create the main event folder
        os.makedirs(pdf_folder, exist_ok=True)  # Create the PDF ticket folder
        os.makedirs(signatures_folder, exist_ok=True)  # Create the Signatures folder

        print(f"✅ Event folder created: {event_folder}")
        print(f"✅ PDF tickets folder created: {pdf_folder}")
        print(f"✅ Signatures folder created: {signatures_folder}")


@receiver(pre_delete, sender=Event)
def delete_event_folder(sender, instance, **kwargs):
    """Deletes the event folder when an event is removed."""
    event_folder = instance.get_event_folder()

    if os.path.exists(event_folder):
        shutil.rmtree(event_folder)  # Remove event directory with all files
        print(f"🗑 Event folder deleted: {event_folder}")


@receiver(post_save, sender=Participant)
def generate_qr_and_pdf(sender, instance, created, **kwargs):
    if created:
        instance.generate_qr_code()
        instance.save()
        generate_pdf_ticket(instance)
