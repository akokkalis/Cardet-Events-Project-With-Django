from xhtml2pdf import pisa
from django.core.files.base import ContentFile
from django.conf import settings
import os
from io import BytesIO  # ✅ This is the missing import
from django.template.loader import render_to_string
import re
from django.core.mail import send_mail, BadHeaderError
from django.core.mail.backends.smtp import EmailBackend
from django.conf import settings


def generate_pdf_ticket(participant, qr_code_path):
    """Generate a PDF ticket using an HTML template."""

    # ✅ Ensure the event's PDF tickets folder exists
    pdf_folder = os.path.join(
        settings.MEDIA_ROOT,
        f"Events/{participant.event.id}_{participant.event.event_name.replace(' ', '_')}/pdf_tickets",
    )
    os.makedirs(pdf_folder, exist_ok=True)

    # ✅ Sanitize filename (replace spaces with underscores)
    sanitized_name = re.sub(
        r"\s+", "_", participant.name.strip()
    )  # Replace spaces with underscores
    sanitized_email = participant.email.replace("@", "_").replace(".", "_")
    pdf_filename = f"{sanitized_name}_{sanitized_email}_ticket.pdf"

    pdf_path = os.path.join(pdf_folder, pdf_filename)

    # ✅ Fix QR Code Path
    qr_image_path = participant.qr_code.url
    qr_image_url = f"{settings.MEDIA_URL}{qr_image_path}".replace("\\", "/")

    # ✅ Generate HTML from template
    html_content = render_to_string(
        "pdf_template.html",
        {
            "participant": participant,
            "qr_image_path": qr_image_path[1:],  # Convert to relative path
        },
    )

    # ✅ Generate PDF from HTML and store in memory buffer
    pdf_buffer = BytesIO()
    pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)

    if pisa_status.err:
        print("❌ Error creating PDF")
        return None

    # ✅ Convert buffer to Django ContentFile
    pdf_content = ContentFile(pdf_buffer.getvalue())

    # ✅ Ensure the correct relative path for saving
    relative_pdf_path = f"Events/{participant.event.id}_{participant.event.event_name.replace(' ', '_')}/pdf_tickets/{pdf_filename}"

    # ✅ Save the PDF content directly to the model field
    participant.pdf_ticket.save(relative_pdf_path, pdf_content, save=False)

    return (
        relative_pdf_path  # Return relative path to store in `participant.pdf_ticket`
    )
