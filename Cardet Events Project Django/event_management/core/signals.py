import os
import shutil
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.conf import settings
from django.core.mail import EmailMessage
from .models import Company, Event, Participant
from .utils import generate_pdf_ticket

COMPANY_MASTER_FOLDER = os.path.join(settings.MEDIA_ROOT, "Companies")
EVENTS_MASTER_FOLDER = os.path.join(settings.MEDIA_ROOT, "Events")


### **Company Folder Creation & Logo Handling**
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


### **Event Folder Creation**
@receiver(post_save, sender=Event)
def create_event_folder(sender, instance, created, **kwargs):
    """Creates an event folder and subfolders for PDFs, Signatures, QR Codes, and moves the image when an event is added."""
    if instance.id is None:  # Ensure instance is fully saved
        return

    event_folder = instance.get_event_folder()
    pdf_folder = os.path.join(event_folder, "pdf_tickets")
    signatures_folder = os.path.join(event_folder, "signatures")
    qr_codes_folder = os.path.join(event_folder, "qr_codes")
    image_folder = os.path.join(event_folder, "event_image")

    if created:
        os.makedirs(event_folder, exist_ok=True)
        os.makedirs(pdf_folder, exist_ok=True)
        os.makedirs(signatures_folder, exist_ok=True)
        os.makedirs(qr_codes_folder, exist_ok=True)
        os.makedirs(image_folder, exist_ok=True)

        print(f"✅ Event folder created: {event_folder}")
        print(f"✅ PDF tickets folder created: {pdf_folder}")
        print(f"✅ Signatures folder created: {signatures_folder}")
        print(f"✅ QR Codes folder created: {qr_codes_folder}")
        print(f"✅ Image folder created: {image_folder}")

    # ✅ Move the event image if necessary
    if instance.image and instance.image.name.startswith("temp/"):
        old_path = os.path.join(settings.MEDIA_ROOT, instance.image.name)
        new_path = os.path.join(image_folder, os.path.basename(instance.image.name))

        if os.path.exists(old_path):
            shutil.move(old_path, new_path)
            instance.image.name = os.path.relpath(new_path, settings.MEDIA_ROOT)
            instance.save(update_fields=["image"])
            print(f"🔄 Event image moved to: {instance.image.name}")


### **Event Folder Deletion on Event Removal**
@receiver(pre_delete, sender=Event)
def delete_event_folder(sender, instance, **kwargs):
    """Deletes the event folder when an event is removed."""
    event_folder = instance.get_event_folder()

    if os.path.exists(event_folder):
        shutil.rmtree(event_folder)  # Remove event directory with all files
        print(f"🗑 Event folder deleted: {event_folder}")


## **QR Code & PDF Ticket Generation for Participants**
@receiver(post_save, sender=Participant)
def generate_qr_and_pdf(sender, instance, created, **kwargs):
    """Generates a QR code and a PDF ticket when a participant is registered."""
    if created:
        qr_path = instance.generate_qr_code()  # Generate and get correct QR path
        pdf_path = generate_pdf_ticket(instance, qr_path)  # Generate PDF

        if pdf_path:  # Only save if the PDF was generated successfully
            instance.pdf_ticket = pdf_path
            instance.save(update_fields=["pdf_ticket"])


### **Email Ticket to Participant**
def send_ticket_email(participant):
    """Send email with the ticket attached."""
    subject = f"Your Ticket for {participant.event.event_name}"
    body = f"""
    Dear {participant.name},

    Thank you for registering for {participant.event.event_name} on {participant.event.event_date} at {participant.event.location}.
    
    Please find your ticket attached. Show this at the entrance for check-in.

    Regards,
    {participant.event.company.name}
    """

    email = EmailMessage(
        subject, body, settings.DEFAULT_FROM_EMAIL, [participant.email]
    )
    email.attach_file(participant.pdf_ticket.path)
    email.send()
