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
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from django.http import HttpResponse
import csv
from django.conf import settings
from .models import Event
from django.core.files.storage import default_storage
import base64
import shutil
from datetime import datetime
from django.urls import reverse
from weasyprint import HTML


def generate_pdf_ticket(participant, qr_code_path):
    """Generate a PDF ticket using an HTML template (WeasyPrint)."""

    # ✔ Create folders
    pdf_folder = os.path.join(
        settings.MEDIA_ROOT,
        f"Events/{participant.event.id}_{participant.event.event_name.replace(' ', '_')}/pdf_tickets",
    )
    os.makedirs(pdf_folder, exist_ok=True)

    # ✔ Sanitize file name
    sanitized_name = re.sub(r"\s+", "_", participant.name.strip())
    sanitized_email = participant.email.replace("@", "_").replace(".", "_")
    pdf_filename = f"{sanitized_name}_{sanitized_email}_ticket.pdf"
    pdf_path = os.path.join(pdf_folder, pdf_filename)

    # ✔ Paths for assets (absolute file paths required)
    qr_image_path = participant.qr_code.path
    logo_path = (
        participant.event.company.logo.path if participant.event.company.logo else None
    )
    event_img_path = participant.event.image.path if participant.event.image else None
    font_path = os.path.join(settings.BASE_DIR, "core", "fonts", "DejaVuSans.ttf")

    # ✔ Render HTML with asset paths
    html_content = render_to_string(
        "ticket_test.html",
        {
            "participant": participant,
            "qr_image_path": qr_image_path,
            "company_logo_path": logo_path,
            "event_image_path": event_img_path,
            "font_path": font_path,
        },
    )

    # ✔ Generate PDF
    pdf_buffer = BytesIO()
    HTML(string=html_content, base_url=settings.BASE_DIR).write_pdf(target=pdf_buffer)

    # ✔ Save as Django File
    pdf_content = ContentFile(pdf_buffer.getvalue())
    relative_pdf_path = f"Events/{participant.event.id}_{participant.event.event_name.replace(' ', '_')}/pdf_tickets/{pdf_filename}"
    participant.pdf_ticket.save(relative_pdf_path, pdf_content, save=False)

    return relative_pdf_path


# def generate_pdf_ticket(participant, qr_code_path):
#     """Generate a PDF ticket using an HTML template."""

#     site_url = f"{settings.SITE_URL}"

#     # ✅ Ensure the event's PDF tickets folder exists
#     pdf_folder = os.path.join(
#         settings.MEDIA_ROOT,
#         f"Events/{participant.event.id}_{participant.event.event_name.replace(' ', '_')}/pdf_tickets",
#     )
#     os.makedirs(pdf_folder, exist_ok=True)

#     # ✅ Sanitize filename (replace spaces with underscores)
#     sanitized_name = re.sub(
#         r"\s+", "_", participant.name.strip()
#     )  # Replace spaces with underscores
#     sanitized_email = participant.email.replace("@", "_").replace(".", "_")
#     pdf_filename = f"{sanitized_name}_{sanitized_email}_ticket.pdf"

#     pdf_path = os.path.join(pdf_folder, pdf_filename)

#     # ✅ Fix QR Code Path
#     qr_image_path = participant.qr_code.url
#     qr_image_url = f"{settings.MEDIA_URL}{qr_image_path}".replace("\\", "/")

#     font_path = os.path.join(settings.BASE_DIR, "core", "fonts", "DejaVuSans.ttf")
#     print("MY FONT URL:", font_path)
#     company_logo_url = (
#         f"{participant.event.company.logo.url}"
#         if participant.event.company.logo
#         else None
#     )
#     print(company_logo_url)

#     event_image_url = (
#         f"{participant.event.image.url}" if participant.event.image else None
#     )
#     print(event_image_url)
#     # ✅ Generate HTML from template
#     html_content = render_to_string(
#         "ticket_test.html",
#         {
#             "participant": participant,
#             "qr_image_path": qr_image_path[1:],  # Convert to relative path
#             "company_logo_url": company_logo_url,
#             "event_image_url": event_image_url,
#             "font_path": font_path.replace("\\", "/"),
#         },
#     )

#     # ✅ Generate PDF from HTML and store in memory buffer
#     pdf_buffer = BytesIO()
#     pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)

#     if pisa_status.err:
#         print("❌ Error creating PDF")
#         return None

#     # ✅ Convert buffer to Django ContentFile
#     pdf_content = ContentFile(pdf_buffer.getvalue())

#     # ✅ Ensure the correct relative path for saving
#     relative_pdf_path = f"Events/{participant.event.id}_{participant.event.event_name.replace(' ', '_')}/pdf_tickets/{pdf_filename}"

#     # ✅ Save the PDF content directly to the model field
#     participant.pdf_ticket.save(relative_pdf_path, pdf_content, save=False)

#     return (
#         relative_pdf_path  # Return relative path to store in `participant.pdf_ticket`
#     )


def email_body(participant_name, event_info):
    """Generate the email body with dynamic participant and event details."""
    location_html = (
        f"""
        📍 <a href="{event_info['location']}" target="_blank" style="color: #1a73e8; text-decoration: none;">
            View Location on Google Maps
        </a>
    """
        if event_info["location"]
        else "📍 Location: Not Provided"
    )
    body = f"""
        <h4>Dear {participant_name},</h4>
        <p>Thank you for your booking! Please find your ticket(s) attached to this email.</p>

        <p><strong>Event Details:</strong></p>
        <p>📅 Event: {event_info['title']}</p>
        {location_html}
        <p>🕒 Date & Time: {event_info['date']} at {event_info['starttime']} - {event_info['endtime']}</p>
        
        <h5>Important Information:</h5>
        <p>✅ Please bring this ticket (printed or digital) for entry.</p>
        <p>✅ Ensure your QR code or barcode is visible for scanning at the entrance.</p>
        <p>✅ Doors open at: {event_info['starttime']} - Arrive early to secure your spot.</p>
        <p>✅ For any inquiries, contact us at: events@cardet.org</p>



        <p>We look forward to seeing you at the event! 🎉</p>

        <p>Best regards,</p>
        <p>Cardet Team</p>
        <p><a href="https://www.cardet.org">Visit cardet.com</a></p> 
    """
    return body


def export_participants_csv(event_id):
    """Exports participants list as CSV and saves signature images in the same folder."""
    event = Event.objects.get(id=event_id)  # ✅ Fetch event
    csv_folder = os.path.join(
        settings.MEDIA_ROOT, f"Exports/{event.event_name.replace(' ', '_')}"
    )
    os.makedirs(csv_folder, exist_ok=True)  # ✅ Ensure folder exists
    csv_path = os.path.join(csv_folder, f"{event.event_name}_participants.csv")

    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)

        # ✅ Write Event Details
        writer.writerow(["Event Name", event.event_name])
        writer.writerow(["Date", event.event_date])
        writer.writerow(["Location", event.location])
        writer.writerow(["Description", event.description])
        writer.writerow(["Status", event.status.name])
        writer.writerow([])  # Empty row for spacing

        # ✅ Get custom fields for headers
        custom_fields = event.custom_fields.all().order_by("order")

        # ✅ Write Table Headers (including custom fields)
        headers = ["#", "Name", "Email", "Phone"]
        for field in custom_fields:
            headers.append(field.label)
        headers.append("Signature Image")
        writer.writerow(headers)

        # ✅ Fetch all participants
        participants = event.participant_set.prefetch_related("attendance_set").all()

        for i, participant in enumerate(participants, start=1):
            attendance = participant.attendance_set.first()
            signature_path = "Not Signed"

            # ✅ Copy Signature File to the CSV Folder
            if attendance and attendance.signature_file:
                original_path = os.path.join(
                    settings.MEDIA_ROOT, attendance.signature_file.name
                )
                if os.path.exists(original_path):
                    new_filename = f"{participant.name.replace(' ', '_')}_signature.png"
                    new_path = os.path.join(csv_folder, new_filename)
                    shutil.copy(original_path, new_path)  # ✅ Copy image file
                    signature_path = new_filename  # ✅ Use relative filename

            # ✅ Build row data including custom fields
            row_data = [
                i,
                participant.name,
                participant.email,
                participant.phone or "-",
            ]

            # ✅ Add custom field data
            for field in custom_fields:
                if (
                    participant.submitted_data
                    and field.label in participant.submitted_data
                ):
                    value = participant.submitted_data[field.label]

                    # Handle different field types for CSV export
                    if isinstance(value, list):
                        # Handle multiselect (array of values)
                        formatted_value = ", ".join(value) if value else "-"
                    elif isinstance(value, bool):
                        # Handle checkbox (boolean)
                        formatted_value = "Yes" if value else "No"
                    elif field.field_type in ["date", "time", "datetime"] and value:
                        # Handle date/time fields with formatting
                        try:
                            if field.field_type == "date":
                                # Format date (YYYY-MM-DD)
                                from datetime import datetime

                                date_obj = datetime.strptime(value, "%Y-%m-%d")
                                formatted_value = date_obj.strftime("%B %d, %Y")
                            elif field.field_type == "time":
                                # Format time (HH:MM)
                                from datetime import datetime

                                time_obj = datetime.strptime(value, "%H:%M")
                                formatted_value = time_obj.strftime("%I:%M %p")
                            elif field.field_type == "datetime":
                                # Format datetime (YYYY-MM-DDTHH:MM)
                                from datetime import datetime

                                datetime_obj = datetime.fromisoformat(value)
                                formatted_value = datetime_obj.strftime(
                                    "%B %d, %Y at %I:%M %p"
                                )
                            else:
                                formatted_value = str(value)
                        except (ValueError, TypeError):
                            # If parsing fails, use the raw value
                            formatted_value = str(value) if value is not None else "-"
                    else:
                        # Handle other types (text, number, email, range, etc.)
                        formatted_value = str(value) if value is not None else "-"
                else:
                    formatted_value = "-"

                row_data.append(formatted_value)

            row_data.append(signature_path)
            writer.writerow(row_data)

    # ✅ Return CSV as Response
    with open(csv_path, "rb") as f:
        response = HttpResponse(f, content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="{event.event_name}_participants.csv"'
        )
        return response


def export_participants_pdf(event_id):
    """Exports participants list as PDF with embedded signature images."""
    event = Event.objects.get(id=event_id)  # ✅ Fetch event
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{event.event_name}_participants.pdf"'
    )

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=landscape(letter))

    # ✅ Event Details
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(30, 550, f"Event: {event.event_name}")
    pdf.drawString(30, 530, f"Date: {event.event_date}")
    pdf.drawString(30, 510, f"Location: {event.location}")
    pdf.drawString(30, 490, f"Description: {event.description}")
    pdf.drawString(30, 470, f"Status: {event.status.name}")

    # ✅ Get custom fields for headers
    custom_fields = event.custom_fields.all().order_by("order")

    # ✅ Table Headers (with dynamic positioning for custom fields)
    y = 440
    pdf.setFont("Helvetica-Bold", 10)
    x_positions = [30, 100, 250, 400]  # Base positions for #, Name, Email, Phone

    pdf.drawString(x_positions[0], y, "#")
    pdf.drawString(x_positions[1], y, "Name")
    pdf.drawString(x_positions[2], y, "Email")
    pdf.drawString(x_positions[3], y, "Phone")

    # Add custom field headers (with limited space)
    current_x = 500
    custom_field_positions = []
    for field in custom_fields:
        if current_x < 750:  # Check if we have space on the page
            pdf.drawString(
                current_x,
                y,
                field.label[:10] + "..." if len(field.label) > 10 else field.label,
            )
            custom_field_positions.append(current_x)
            current_x += 80
        else:
            # If we run out of space, we'll truncate remaining fields
            break

    # Signature column at the end
    signature_x = current_x if current_x < 750 else 750
    pdf.drawString(signature_x, y, "Signature")

    # ✅ Fetch all participants
    y -= 20
    pdf.setFont("Helvetica", 10)
    participants = event.participant_set.prefetch_related("attendance_set").all()

    for i, participant in enumerate(participants, start=1):
        # Check if we need a new page
        if y < 50:
            pdf.showPage()
            y = 750

        pdf.drawString(x_positions[0], y, str(i))
        pdf.drawString(
            x_positions[1],
            y,
            (
                participant.name[:15] + "..."
                if len(participant.name) > 15
                else participant.name
            ),
        )
        pdf.drawString(
            x_positions[2],
            y,
            (
                participant.email[:20] + "..."
                if len(participant.email) > 20
                else participant.email
            ),
        )
        pdf.drawString(
            x_positions[3],
            y,
            (
                participant.phone[:12] + "..."
                if participant.phone and len(participant.phone) > 12
                else participant.phone or "-"
            ),
        )

        # Add custom field data
        for j, field in enumerate(custom_fields):
            if j < len(custom_field_positions):  # Only show fields that fit on the page
                if (
                    participant.submitted_data
                    and field.label in participant.submitted_data
                ):
                    value = participant.submitted_data[field.label]

                    # Handle different field types for PDF export
                    if isinstance(value, list):
                        # Handle multiselect (array of values)
                        formatted_value = (
                            ", ".join(value[:2]) + "..."
                            if len(value) > 2
                            else ", ".join(value) if value else "-"
                        )
                    elif isinstance(value, bool):
                        # Handle checkbox (boolean)
                        formatted_value = "Yes" if value else "No"
                    elif field.field_type in ["date", "time", "datetime"] and value:
                        # Handle date/time fields with compact formatting for PDF
                        try:
                            if field.field_type == "date":
                                # Format date compactly (MM/DD/YY)
                                from datetime import datetime

                                date_obj = datetime.strptime(value, "%Y-%m-%d")
                                formatted_value = date_obj.strftime("%m/%d/%y")
                            elif field.field_type == "time":
                                # Format time compactly (HH:MM)
                                formatted_value = (
                                    value  # Keep as-is (HH:MM format is compact)
                                )
                            elif field.field_type == "datetime":
                                # Format datetime compactly (MM/DD HH:MM)
                                from datetime import datetime

                                datetime_obj = datetime.fromisoformat(value)
                                formatted_value = datetime_obj.strftime("%m/%d %H:%M")
                            else:
                                formatted_value = (
                                    str(value)[:8] + "..."
                                    if len(str(value)) > 8
                                    else str(value)
                                )
                        except (ValueError, TypeError):
                            # If parsing fails, use truncated raw value
                            formatted_value = (
                                str(value)[:8] + "..."
                                if len(str(value)) > 8
                                else str(value) if value is not None else "-"
                            )
                    else:
                        # Handle other types (text, number, email, range, etc.)
                        formatted_value = (
                            str(value)[:10] + "..."
                            if len(str(value)) > 10
                            else str(value) if value is not None else "-"
                        )
                else:
                    formatted_value = "-"

                pdf.drawString(custom_field_positions[j], y, formatted_value)

        attendance = participant.attendance_set.first()

        # ✅ Embed Signature Image
        if attendance and attendance.signature_file:
            signature_path = os.path.join(
                settings.MEDIA_ROOT, attendance.signature_file.name
            )
            if os.path.exists(signature_path):
                img = ImageReader(signature_path)
                pdf.drawImage(
                    img, signature_x, y - 10, width=50, height=20
                )  # Adjust dimensions
            else:
                pdf.drawString(signature_x, y, "Missing")
        else:
            pdf.drawString(signature_x, y, "Not Signed")

        y -= 25  # Move to next row (increased spacing for better readability)

    pdf.save()
    buffer.seek(0)
    response.write(buffer.getvalue())
    return response


def generate_ics_file(event):
    """Generate .ics file for the event."""

    # Get the domain dynamically

    # Prepare event details
    event_name = event.event_name
    event_start = (
        event.event_date.strftime("%Y%m%d") + "T" + event.start_time.strftime("%H%M%S")
    )
    event_end = (
        event.event_date.strftime("%Y%m%d") + "T" + event.end_time.strftime("%H%M%S")
    )
    event_location = event.location or "Location Not Provided"
    event_description = event.description or "No description available"

    # Create .ics file content
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Your App//Event Management//EN
BEGIN:VEVENT
UID:{event.uuid}@yourdomain.com
DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%S')}
DTSTART:{event_start}
DTEND:{event_end}
SUMMARY:{event_name}
DESCRIPTION:{event_description}
LOCATION:{event_location}
ORGANIZER;CN={event.company.name}:MAILTO:{event.company.email}
END:VEVENT
END:VCALENDAR
"""

    # Save to a file or return as content
    file_path = os.path.join(settings.MEDIA_ROOT, f"Events/{event.id}_event.ics")
    with open(file_path, "w") as f:
        f.write(ics_content)

    return file_path


def generate_rsvp_urls(participant, request_or_site_url=None):
    """Generate RSVP URLs for email templates."""
    from django.urls import reverse

    # Get the base URL - either from request or settings
    if hasattr(request_or_site_url, "build_absolute_uri"):
        # It's a request object
        base_url = request_or_site_url.build_absolute_uri("/")[
            :-1
        ]  # Remove trailing slash
    elif isinstance(request_or_site_url, str):
        # It's a site URL string
        base_url = request_or_site_url.rstrip("/")
    else:
        # Fallback to settings
        base_url = getattr(settings, "SITE_URL", "http://127.0.0.1:8000").rstrip("/")

    # Generate the RSVP URLs
    rsvp_urls = {
        "rsvp_accept_url": base_url
        + reverse(
            "rsvp_response",
            kwargs={
                "event_uuid": participant.event.uuid,
                "participant_id": participant.id,
                "response": "attend",
            },
        ),
        "rsvp_decline_url": base_url
        + reverse(
            "rsvp_response",
            kwargs={
                "event_uuid": participant.event.uuid,
                "participant_id": participant.id,
                "response": "cant_make_it",
            },
        ),
        "rsvp_maybe_url": base_url
        + reverse(
            "rsvp_response",
            kwargs={
                "event_uuid": participant.event.uuid,
                "participant_id": participant.id,
                "response": "maybe",
            },
        ),
    }

    return rsvp_urls


def generate_certificate_for_participant(event, participant):
    """
    Generate certificate for a single participant using the proven working logic.
    Extracted from generate_participant_certificate view to be reusable.
    Returns (success: bool, message: str)
    """
    import tempfile
    import os
    import pypdf
    from django.core.files.base import ContentFile
    import logging

    logger = logging.getLogger(__name__)

    try:
        print(f"=== CERTIFICATE GENERATION FOR {participant.name} ===")

        if not event.certificate:
            return False, "No certificate template found for this event."

        file_extension = os.path.splitext(event.certificate.name)[1].lower()
        if file_extension != ".pdf":
            return False, "Certificate template must be a PDF file."

        # Prepare form data to fill
        form_data = {
            "participant_name": participant.name,
            "event_name": event.event_name,
            "event_date": (
                event.event_date.strftime("%d %B %Y") if event.event_date else ""
            ),
            "company_name": event.company.name if event.company else "",
        }

        # Save the template PDF to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_input:
            with event.certificate.open("rb") as f:
                temp_input.write(f.read())
            temp_input_path = temp_input.name

        # Read the PDF template (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
        reader = pypdf.PdfReader(temp_input_path)

        # Check if PDF has pages (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
        if len(reader.pages) == 0:
            raise Exception(
                "The PDF file has no pages. This might be due to a failed DOCX to PDF conversion or a corrupted file."
            )

        print(f"PDF has {len(reader.pages)} page(s)")
        writer = pypdf.PdfWriter()
        writer.add_page(reader.pages[0])

        # Check if the PDF has form fields (AcroForm) (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
        has_form_fields = False
        try:
            form_fields = reader.get_fields()
            if form_fields:
                has_form_fields = True
                print("PDF has form fields (via get_fields):", form_fields.keys())
        except:
            pass

        if not has_form_fields:
            # Check for AcroForm in a different way (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
            try:
                if "/AcroForm" in reader.trailer["/Root"]:
                    has_form_fields = True
                    print("PDF has AcroForm - using form field filling")
            except:
                pass

        if has_form_fields:
            # Try to fill form fields (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
            try:
                writer.update_page_form_field_values(writer.pages[0], form_data)
                print("Successfully filled form fields")
            except Exception as form_error:
                print(f"Form field filling failed: {form_error}")
                has_form_fields = False

        if not has_form_fields:
            print("PDF does not have fillable form fields")
            # Try text-based replacement using PyMuPDF if available (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
            try:
                import fitz  # PyMuPDF

                # Use PyMuPDF for text replacement
                doc = fitz.open(temp_input_path)
                replacements_made = 0

                # Define placeholder patterns to search for (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
                placeholder_patterns = {
                    "participant_name": [
                        "{{participant_name}}",
                        "{{ participant_name }}",
                        "{participant_name}",
                        "{ participant_name }",
                        "[participant_name]",
                        "[ participant_name ]",
                        "__PARTICIPANT_NAME__",
                        "_PARTICIPANT_NAME_",
                    ],
                    "event_name": [
                        "{{event_name}}",
                        "{{ event_name }}",
                        "{event_name}",
                        "{ event_name }",
                        "[event_name]",
                        "[ event_name ]",
                        "__EVENT_NAME__",
                        "_EVENT_NAME_",
                    ],
                    "event_date": [
                        "{{event_date}}",
                        "{{ event_date }}",
                        "{event_date}",
                        "{ event_date }",
                        "[event_date]",
                        "[ event_date ]",
                        "__EVENT_DATE__",
                        "_EVENT_DATE_",
                    ],
                    "company_name": [
                        "{{company_name}}",
                        "{{ company_name }}",
                        "{company_name}",
                        "{ company_name }",
                        "[company_name]",
                        "[ company_name ]",
                        "__COMPANY_NAME__",
                        "_COMPANY_NAME_",
                    ],
                }

                for page_num in range(len(doc)):
                    page = doc[page_num]

                    # Store replacement info for styled insertion after redaction
                    styled_replacements = []

                    # Replace placeholders (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
                    for field_name, patterns in placeholder_patterns.items():
                        if field_name in form_data and form_data[field_name]:
                            for pattern in patterns:
                                # Search and replace text
                                text_instances = page.search_for(pattern)
                                for inst in text_instances:
                                    # Get the original text properties to preserve styling
                                    try:
                                        # Get text details from the location
                                        blocks = page.get_text("dict", clip=inst)

                                        # Try to extract font information from the original text
                                        font_name = "helv"  # Default font
                                        font_size = 12  # Default size
                                        font_flags = 0  # Default flags
                                        color = (0, 0, 0)  # Default black

                                        if blocks and "blocks" in blocks:
                                            for block in blocks["blocks"]:
                                                if "lines" in block:
                                                    for line in block["lines"]:
                                                        if "spans" in line:
                                                            for span in line["spans"]:
                                                                span_text = span.get(
                                                                    "text", ""
                                                                ).lower()
                                                                if (
                                                                    pattern.lower()
                                                                    in span_text
                                                                ):
                                                                    font_name = (
                                                                        span.get(
                                                                            "font",
                                                                            "helv",
                                                                        )
                                                                    )
                                                                    font_size = (
                                                                        span.get(
                                                                            "size", 12
                                                                        )
                                                                    )
                                                                    font_flags = (
                                                                        span.get(
                                                                            "flags", 0
                                                                        )
                                                                    )
                                                                    color = span.get(
                                                                        "color", 0
                                                                    )

                                                                    # Handle color conversion
                                                                    if isinstance(
                                                                        color, int
                                                                    ):
                                                                        # Convert integer color to RGB tuple
                                                                        if (
                                                                            color != 0
                                                                        ):  # Only convert if not default
                                                                            color = (
                                                                                (
                                                                                    color
                                                                                    >> 16
                                                                                )
                                                                                & 255,
                                                                                (
                                                                                    color
                                                                                    >> 8
                                                                                )
                                                                                & 255,
                                                                                color
                                                                                & 255,
                                                                            )
                                                                            color = tuple(
                                                                                c
                                                                                / 255.0
                                                                                for c in color
                                                                            )
                                                                        else:
                                                                            color = (
                                                                                0,
                                                                                0,
                                                                                0,
                                                                            )  # Default black
                                                                    elif isinstance(
                                                                        color,
                                                                        (list, tuple),
                                                                    ):
                                                                        # Already a tuple/list, normalize to 0-1 range
                                                                        color = tuple(
                                                                            (
                                                                                c
                                                                                / 255.0
                                                                                if c > 1
                                                                                else c
                                                                            )
                                                                            for c in color
                                                                        )
                                                                    break

                                        # Calculate text position for replacement
                                        replacement_text = form_data[field_name]

                                        # Calculate center position
                                        center_x = (inst.x0 + inst.x1) / 2
                                        center_y = (inst.y0 + inst.y1) / 2

                                        # Calculate starting position for left alignment
                                        original_width = inst.x1 - inst.x0
                                        estimated_char_width = font_size * 0.6
                                        estimated_text_width = (
                                            len(replacement_text) * estimated_char_width
                                        )

                                        if estimated_text_width < original_width:
                                            text_x = (
                                                inst.x0
                                                + (
                                                    original_width
                                                    - estimated_text_width
                                                )
                                                / 2
                                            )
                                        else:
                                            text_x = inst.x0

                                        text_y = center_y

                                        styled_replacements.append(
                                            {
                                                "position": fitz.Point(text_x, text_y),
                                                "text": replacement_text,
                                                "font": font_name,
                                                "size": font_size,
                                                "color": color,
                                            }
                                        )

                                        # Add redaction annotation to remove original text
                                        page.add_redact_annot(inst, "")
                                        replacements_made += 1

                                    except Exception as e:
                                        print(f"Error processing text replacement: {e}")
                                        # Fallback with basic replacement
                                        replacement_text = form_data[field_name]
                                        center_x = (inst.x0 + inst.x1) / 2
                                        center_y = (inst.y0 + inst.y1) / 2

                                        # Calculate starting position for left alignment
                                        original_width = inst.x1 - inst.x0
                                        estimated_char_width = (
                                            12 * 0.6
                                        )  # Default font size
                                        estimated_text_width = (
                                            len(replacement_text) * estimated_char_width
                                        )

                                        if estimated_text_width < original_width:
                                            text_x = (
                                                inst.x0
                                                + (
                                                    original_width
                                                    - estimated_text_width
                                                )
                                                / 2
                                            )
                                        else:
                                            text_x = inst.x0

                                        text_y = center_y

                                        styled_replacements.append(
                                            {
                                                "position": fitz.Point(text_x, text_y),
                                                "text": replacement_text,
                                                "font": "helv",
                                                "size": 12,
                                                "color": (0, 0, 0),
                                            }
                                        )

                                        page.add_redact_annot(inst, "")
                                        replacements_made += 1

                # Apply all redactions first (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    page.apply_redactions()

                # Then insert all the styled text replacements (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    for replacement in styled_replacements:
                        try:
                            page.insert_text(
                                replacement["position"],
                                replacement["text"],
                                fontsize=replacement["size"],
                                color=replacement["color"],
                            )
                        except Exception as insert_error:
                            print(f"Error inserting styled text: {insert_error}")
                            # Try basic insertion
                            try:
                                page.insert_text(
                                    replacement["position"], replacement["text"]
                                )
                            except Exception as basic_error:
                                print(
                                    f"Basic text insertion also failed: {basic_error}"
                                )

                # Save the modified document if we made replacements (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
                if replacements_made > 0:
                    print(f"Made {replacements_made} text replacements")
                    # Save to a new temporary file
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".pdf"
                    ) as temp_modified:
                        temp_modified_path = temp_modified.name

                    # Save the modified document
                    doc.save(temp_modified_path, garbage=4, deflate=True)
                    doc.close()

                    # Replace the original temp file with the modified one
                    try:
                        os.remove(temp_input_path)
                        os.rename(temp_modified_path, temp_input_path)
                    except Exception as file_error:
                        print(f"Error replacing temp file: {file_error}")
                        # If rename fails, use the new file
                        temp_input_path = temp_modified_path

                    # Re-read the PDF with pypdf
                    reader = pypdf.PdfReader(temp_input_path)
                    writer = pypdf.PdfWriter()
                    writer.add_page(reader.pages[0])
                else:
                    print("No text placeholders found for replacement")
                    doc.close()

            except ImportError:
                print("PyMuPDF not available - using basic PDF processing")
            except Exception as text_error:
                print(f"Text replacement failed: {text_error}")

        # Add metadata if available (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
        if hasattr(reader, "metadata") and reader.metadata:
            writer.add_metadata(reader.metadata)

        # Save the final PDF (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_output:
            writer.write(temp_output)
            temp_output_path = temp_output.name

        # Read the final PDF content (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
        with open(temp_output_path, "rb") as output_file:
            filled_pdf = output_file.read()

        # Save the certificate to the participant model (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
        filename = f"certificate_{participant.name.replace(' ', '_')}.pdf"
        participant.certificate.save(filename, ContentFile(filled_pdf), save=True)

        # Clean up temporary files (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
        try:
            if os.path.exists(temp_input_path):
                os.remove(temp_input_path)
        except Exception as cleanup_error:
            print(f"Error cleaning up temp_input_path: {cleanup_error}")

        try:
            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)
        except Exception as cleanup_error:
            print(f"Error cleaning up temp_output_path: {cleanup_error}")

        print(f"Certificate generated successfully for {participant.name}")
        return True, f"Certificate generated successfully for {participant.name}"

    except Exception as e:
        logger.exception("Failed to generate certificate")
        error_msg = f"Failed to generate certificate for {participant.name}: {str(e)}"
        print(error_msg)
        return False, error_msg
