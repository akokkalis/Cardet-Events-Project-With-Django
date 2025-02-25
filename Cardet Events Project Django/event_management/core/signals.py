import os
import shutil
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.conf import settings
from django.core.mail import EmailMessage
from .models import Company, Event, Participant
from .utils import generate_pdf_ticket, email_body
import threading
from django.core.mail import EmailMessage, get_connection
from django.utils.html import strip_tags

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
        if instance.event.tickets:  # ✅ Check if tickets are enabled
            qr_path = instance.generate_qr_code()  # Generate and get correct QR path
            pdf_path = generate_pdf_ticket(instance, qr_path)  # Generate PDF

            if pdf_path:  # Only save if the PDF was generated successfully
                instance.pdf_ticket = pdf_path
                instance.save(update_fields=["pdf_ticket"])
                # ✅ Send email asynchronously with PDF ticket
                send_ticket_email(instance)
        else:
            print(
                f"🚫 Skipping QR & PDF: Tickets are disabled for {instance.event.event_name}"
            )


### **Email Ticket to Participant**


def send_ticket_email(participant):
    """Send an email with the event ticket attached asynchronously using the company's SMTP settings."""

    # ✅ Get company email configuration
    email_config = getattr(participant.event.company, "email_config", None)
    if not email_config:
        print(f"⚠️ No email configuration found for {participant.event.company.name}")
        return

    # ✅ Email subject & body
    subject = f"Your Ticket for {participant.event.event_name}"
    # ✅ Prepare Event Information
    event_info = {
        "title": participant.event.event_name,
        "location": participant.event.location,
        "date": participant.event.event_date.strftime("%d-%m-%y"),
        "starttime": (
            participant.event.start_time.strftime("%H:%M")
            if participant.event.start_time
            else "TBA"
        ),
        "endtime": (
            participant.event.end_time.strftime("%H:%M")
            if participant.event.end_time
            else "TBA"
        ),
    }

    # ✅ Generate email body with correct parameters
    html_message = email_body(participant.name, event_info)
    plain_message = strip_tags(
        html_message
    )  # Remove HTML tags for plaintext email fallback

    # ✅ Attach PDF Ticket
    pdf_path = participant.pdf_ticket.path if participant.pdf_ticket else None

    # ✅ Create the SMTP connection separately (No `backend` argument)
    connection = get_connection(
        host=email_config.smtp_server,
        port=email_config.smtp_port,
        username=email_config.email_address,
        password=email_config.email_password,
        use_tls=email_config.use_tls,
        use_ssl=email_config.use_ssl,
    )

    # ✅ Define email sending function
    def send_email():
        try:
            email = EmailMessage(
                subject,
                html_message,
                from_email=email_config.email_address,
                to=[participant.email],
                connection=connection,  # Use the configured connection
            )
            email.content_subtype = "html"  # Ensure HTML email formatting

            if pdf_path and os.path.exists(pdf_path):
                email.attach_file(pdf_path)

            email.send()
            print(f"✅ Ticket email sent to {participant.email}")

        except Exception as e:
            print(f"❌ Error sending email to {participant.email}: {e}")

    # ✅ Run the email function in a separate thread (non-blocking)
    email_thread = threading.Thread(target=send_email)
    email_thread.start()
