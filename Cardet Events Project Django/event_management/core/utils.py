from xhtml2pdf import pisa
from django.core.files.base import ContentFile
from django.conf import settings
import os
from io import BytesIO  # ✅ This is the missing import
from django.template.loader import render_to_string


def generate_pdf_ticket(participant, qr_code_path):
    """Generate a PDF ticket using the external HTML template."""

    # ✅ Ensure PDF tickets are saved inside the correct event folder
    pdf_folder = os.path.join(
        settings.MEDIA_ROOT,
        f"Events/{participant.event.id}_{participant.event.event_name.replace(' ','_')}/pdf_tickets",
    )
    os.makedirs(pdf_folder, exist_ok=True)

    sanitized_email = participant.email.replace("@", "_").replace(".", "_")

    pdf_filename = f"{participant.name}_{sanitized_email}_ticket.pdf"

    pdf_path = os.path.join(pdf_folder, pdf_filename)

    # ✅ Fix QR Code Path for PDF
    qr_image_path = participant.qr_code.url  # This should now return a valid media URL

    # ✅ Use Django’s `MEDIA_URL` for serving images
    qr_image_url = f"{settings.MEDIA_URL}{qr_image_path}".replace("\\", "/")

    # ✅ Use `render_to_string` to dynamically generate HTML from template
    html_content = render_to_string(
        "pdf_template.html",
        {
            "participant": participant,
            "qr_image_path": qr_image_path[1:],
            # Convert to absolute path
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

    # ✅ Return correct relative path for saving in the model
    relative_pdf_path = f"Events/{participant.event.id}_{participant.event.event_name.replace(' ', '_')}/pdf_tickets/{pdf_filename}"

    # ✅ Save PDF content directly to the model field without creating a duplicate file
    participant.pdf_ticket.save(relative_pdf_path, pdf_content, save=False)

    return relative_pdf_path  # Return relative path so it can be assigned to participant.pdf_ticket
