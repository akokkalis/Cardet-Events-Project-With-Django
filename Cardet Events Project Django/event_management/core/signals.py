import os
import shutil
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.conf import settings
from django.core.mail import EmailMessage
<<<<<<< HEAD
from .models import (
    Company,
    Event,
    Participant,
    EventEmail,
    Order,
    OrderItem,
    PaidTicket,
)
from .utils import (
    generate_pdf_ticket,
    generate_rsvp_urls,
    email_body,
    generate_ics_file,
)
from django.core.mail import EmailMessage, get_connection
from django.utils.html import strip_tags
from django.template import Template, Context
from .tasks import (
    send_ticket_email_task,
    send_approval_email_task,
    send_rejection_email_task,
    send_registration_email_task,
    send_rsvp_email_task,
    process_registration_task,
    process_approval_task,
    process_rejection_task,
    generate_paidticket_pdf_task,
)

=======
from .models import Company, Event, Participant
from .utils import generate_pdf_ticket
>>>>>>> d159ca2 (File Logic Ready (creating folders for each event , qr codes files and pdf tickets))

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


<<<<<<< HEAD
### **Paid Tickets Folder Creation**
@receiver(post_save, sender=Event)
def create_paid_tickets_folder(sender, instance, **kwargs):
    """Creates a 'Paid Tickets' folder inside the event's folder if paid_tickets is enabled."""
    if instance.paid_tickets:
        event_folder = os.path.join(
            EVENTS_MASTER_FOLDER,
            f"{instance.id}_{instance.event_name.replace(' ', '_')}",
        )
        paid_tickets_folder = os.path.join(event_folder, "paid_tickets")
        os.makedirs(paid_tickets_folder, exist_ok=True)
        print(f"✅ Paid Tickets folder created: {paid_tickets_folder}")


## **QR Code & PDF Ticket Generation for Participants**
@receiver(post_save, sender=Participant)
def generate_qr_and_pdf(sender, instance, created, **kwargs):
    """Handles participant registration logic based on auto_approval and tickets settings."""
    if created:

        # ✅ Run registration processing using Celery task
        task = process_registration_task.delay(instance.id)
        print(
            f"✅ Celery task {task.id} queued for registration processing: {instance.name}"
        )

        print(f"🚀 Registration processing started in background for: {instance.name}")
=======
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
>>>>>>> d159ca2 (File Logic Ready (creating folders for each event , qr codes files and pdf tickets))


### **Email Ticket to Participant**
def send_ticket_email(participant):
<<<<<<< HEAD
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
        "map_link": participant.event.map_link,
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

    # ✅ Generate .ics file for the event
    ics_file_path = generate_ics_file(participant.event)

    # ✅ Create the SMTP connection separately (No `backend` argument)
    connection = get_connection(
        host=email_config.smtp_server,
        port=email_config.smtp_port,
        username=email_config.email_address,
        password=email_config.email_password,
        use_tls=email_config.use_tls,
        use_ssl=email_config.use_ssl,
    )

    # ✅ Send email using Celery task (non-blocking)
    task = send_ticket_email_task.delay(participant.id)
    print(
        f"✅ Celery task {task.id} queued for sending ticket email to {participant.email}"
    )


def send_approval_email(participant):
    """Send an approval email to the participant using custom email templates."""

    # ✅ Get the event's approval email template
    try:
        event_email = EventEmail.objects.get(event=participant.event, reason="approval")
    except EventEmail.DoesNotExist:
        print(f"📧 No approval email template found for {participant.event.event_name}")
        return

    # ✅ Get company email configuration
    email_config = getattr(participant.event.company, "email_config", None)
    if not email_config:
        print(f"⚠️ No email configuration found for {participant.event.company.name}")
        return

    # ✅ Prepare template context with placeholders
    context_data = {
        "name": participant.name,
        "event_name": participant.event.event_name,
        "event_date": participant.event.event_date.strftime("%B %d, %Y"),
        "event_location": participant.event.location or "TBA",
        "start_time": (
            participant.event.start_time.strftime("%I:%M %p")
            if participant.event.start_time
            else "TBA"
        ),
        "end_time": (
            participant.event.end_time.strftime("%I:%M %p")
            if participant.event.end_time
            else "TBA"
        ),
        "email": participant.email,
        "phone": participant.phone or "N/A",
    }

    # ✅ Add RSVP URLs to context for all email templates
    rsvp_urls = generate_rsvp_urls(participant)
    context_data.update(rsvp_urls)

    # ✅ Render the email subject and body with template placeholders
    subject_template = Template(event_email.subject)
    body_template = Template(event_email.body)
    context = Context(context_data)

    rendered_subject = subject_template.render(context)
    rendered_body = body_template.render(context)

    # ✅ Create the SMTP connection
    connection = get_connection(
        host=email_config.smtp_server,
        port=email_config.smtp_port,
        username=email_config.email_address,
        password=email_config.email_password,
        use_tls=email_config.use_tls,
        use_ssl=email_config.use_ssl,
    )

    # ✅ Send email using Celery task (non-blocking)
    task = send_approval_email_task.delay(participant.id)
    print(
        f"✅ Celery task {task.id} queued for sending approval email to {participant.email}"
    )


def send_rejection_email(participant):
    """Send a rejection email to the participant using custom email templates."""

    # ✅ Get the event's rejection email template
    try:
        event_email = EventEmail.objects.get(
            event=participant.event, reason="rejection"
        )
    except EventEmail.DoesNotExist:
        print(
            f"📧 No rejection email template found for {participant.event.event_name}"
        )
        return

    # ✅ Get company email configuration
    email_config = getattr(participant.event.company, "email_config", None)
    if not email_config:
        print(f"⚠️ No email configuration found for {participant.event.company.name}")
        return

    # ✅ Prepare template context with placeholders
    context_data = {
        "name": participant.name,
        "event_name": participant.event.event_name,
        "event_date": participant.event.event_date.strftime("%B %d, %Y"),
        "event_location": participant.event.location or "TBA",
        "start_time": (
            participant.event.start_time.strftime("%I:%M %p")
            if participant.event.start_time
            else "TBA"
        ),
        "end_time": (
            participant.event.end_time.strftime("%I:%M %p")
            if participant.event.end_time
            else "TBA"
        ),
        "email": participant.email,
        "phone": participant.phone or "N/A",
    }

    # ✅ Add RSVP URLs to context for all email templates
    rsvp_urls = generate_rsvp_urls(participant)
    context_data.update(rsvp_urls)

    # ✅ Render the email subject and body with template placeholders
    subject_template = Template(event_email.subject)
    body_template = Template(event_email.body)
    context = Context(context_data)

    rendered_subject = subject_template.render(context)
    rendered_body = body_template.render(context)

    # ✅ Create the SMTP connection
    connection = get_connection(
        host=email_config.smtp_server,
        port=email_config.smtp_port,
        username=email_config.email_address,
        password=email_config.email_password,
        use_tls=email_config.use_tls,
        use_ssl=email_config.use_ssl,
    )

    # ✅ Send email using Celery task (non-blocking)
    task = send_rejection_email_task.delay(participant.id)
    print(
        f"✅ Celery task {task.id} queued for sending rejection email to {participant.email}"
    )


def handle_participant_approval(participant):
    """Handle the approval process for a participant."""

    # ✅ Run approval processing using Celery task
    task = process_approval_task.delay(participant.id)
    print(
        f"✅ Celery task {task.id} queued for approval processing: {participant.name}"
    )

    print(f"🚀 Approval processing started in background for: {participant.name}")


def handle_participant_rejection(participant):
    """Handle the rejection process for a participant."""

    # ✅ Run rejection processing using Celery task
    task = process_rejection_task.delay(participant.id)
    print(
        f"✅ Celery task {task.id} queued for rejection processing: {participant.name}"
    )

    print(f"🚀 Rejection processing started in background for: {participant.name}")


# ✅ We'll handle manual approval/rejection through views or admin actions
# The signals above handle automatic approval on registration


def send_registration_email(participant):
    """Send a registration email to the participant using custom email templates."""

    # ✅ Get the event's registration email template
    try:
        event_email = EventEmail.objects.get(
            event=participant.event, reason="registration"
        )
    except EventEmail.DoesNotExist:
        print(
            f"📧 No registration email template found for {participant.event.event_name}"
        )
        return

    # ✅ Get company email configuration
    email_config = getattr(participant.event.company, "email_config", None)
    if not email_config:
        print(f"⚠️ No email configuration found for {participant.event.company.name}")
        return

    # ✅ Prepare template context with placeholders
    context_data = {
        "name": participant.name,
        "event_name": participant.event.event_name,
        "event_date": participant.event.event_date.strftime("%B %d, %Y"),
        "event_location": participant.event.location or "TBA",
        "start_time": (
            participant.event.start_time.strftime("%I:%M %p")
            if participant.event.start_time
            else "TBA"
        ),
        "end_time": (
            participant.event.end_time.strftime("%I:%M %p")
            if participant.event.end_time
            else "TBA"
        ),
        "email": participant.email,
        "phone": participant.phone or "N/A",
    }

    # ✅ Add RSVP URLs to context for all email templates
    rsvp_urls = generate_rsvp_urls(participant)
    context_data.update(rsvp_urls)

    # ✅ Render the email subject and body with template placeholders
    subject_template = Template(event_email.subject)
    body_template = Template(event_email.body)
    context = Context(context_data)

    rendered_subject = subject_template.render(context)
    rendered_body = body_template.render(context)

    # ✅ Create the SMTP connection
    connection = get_connection(
        host=email_config.smtp_server,
        port=email_config.smtp_port,
        username=email_config.email_address,
        password=email_config.email_password,
        use_tls=email_config.use_tls,
        use_ssl=email_config.use_ssl,
    )

    # ✅ Send email using Celery task (non-blocking)
    task = send_registration_email_task.delay(participant.id)
    print(
        f"✅ Celery task {task.id} queued for sending registration email to {participant.email}"
    )


def send_rsvp_email(participant):
    """Send an RSVP request email to the participant using custom email templates."""

    # ✅ Get the event's RSVP email template
    try:
        event_email = EventEmail.objects.get(event=participant.event, reason="rsvp")
    except EventEmail.DoesNotExist:
        print(f"📧 No RSVP email template found for {participant.event.event_name}")
        return

    # ✅ Get company email configuration
    email_config = getattr(participant.event.company, "email_config", None)
    if not email_config:
        print(f"⚠️ No email configuration found for {participant.event.company.name}")
        return

    # ✅ Prepare template context with placeholders
    context_data = {
        "name": participant.name,
        "event_name": participant.event.event_name,
        "event_date": participant.event.event_date.strftime("%B %d, %Y"),
        "event_location": participant.event.location or "TBA",
        "start_time": (
            participant.event.start_time.strftime("%I:%M %p")
            if participant.event.start_time
            else "TBA"
        ),
        "end_time": (
            participant.event.end_time.strftime("%I:%M %p")
            if participant.event.end_time
            else "TBA"
        ),
        "email": participant.email,
        "phone": participant.phone or "N/A",
    }

    # ✅ Add RSVP URLs to context for RSVP email templates
    rsvp_urls = generate_rsvp_urls(participant)
    print("🔍 RSVP URLs:")
    print(rsvp_urls)
    context_data.update(rsvp_urls)

    # ✅ Render the email subject and body with template placeholders
    subject_template = Template(event_email.subject)
    body_template = Template(event_email.body)
    context = Context(context_data)

    rendered_subject = subject_template.render(context)
    rendered_body = body_template.render(context)

    # ✅ Create the SMTP connection
    connection = get_connection(
        host=email_config.smtp_server,
        port=email_config.smtp_port,
        username=email_config.email_address,
        password=email_config.email_password,
        use_tls=email_config.use_tls,
        use_ssl=email_config.use_ssl,
    )

    # ✅ Send email using Celery task (non-blocking)
    task = send_rsvp_email_task.delay(participant.id)
    print(
        f"✅ Celery task {task.id} queued for sending RSVP email to {participant.email}"
    )


@receiver(post_save, sender=Order)
def generate_paid_tickets_on_order_complete(sender, instance, created, **kwargs):
    """Generate PaidTicket objects and QR codes when an order is marked as completed."""
    if instance.payment_status == "completed":
        print("inside signal pdf gen paid")
        # Only generate if not already generated
        if not PaidTicket.objects.filter(order=instance).exists():
            order_items = OrderItem.objects.filter(order=instance)
            for item in order_items:
                for _ in range(item.quantity):
                    paid_ticket = PaidTicket.objects.create(
                        order=instance,
                        ticket_type=item.ticket_type,
                        participant=instance.participant,
                    )
                    paid_ticket.generate_qr_code()
                    paid_ticket.save()
                    generate_paidticket_pdf_task.delay(paid_ticket.id)
=======
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
>>>>>>> d159ca2 (File Logic Ready (creating folders for each event , qr codes files and pdf tickets))
