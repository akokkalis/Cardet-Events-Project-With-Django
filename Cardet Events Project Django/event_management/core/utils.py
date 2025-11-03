# from xhtml2pdf import pisa
from django.core.files.base import ContentFile
from django.conf import settings
import os
from io import BytesIO  # ✅ This is the missing import
from django.template.loader import render_to_string
import re
from django.core.mail import send_mail, BadHeaderError
from django.core.mail.backends.smtp import EmailBackend
from django.conf import settings

# from reportlab.lib.pagesizes import letter, landscape
# from reportlab.pdfgen import canvas
# from reportlab.lib.utils import ImageReader
from django.http import HttpResponse
import csv
from django.conf import settings
from .models import Event, PaidTicket
from django.core.files.storage import default_storage
import base64
import shutil
from datetime import datetime
from django.urls import reverse
import tempfile
from pathlib import Path

# from weasyprint import HTML

from gotenberg_client import GotenbergClient
from gotenberg_client.options import PdfAFormat


def generate_pdf_ticket(participant, qr_code_path):
    """Generate a PDF ticket using Gotenberg client with HTML template."""

    print("Generating PDF ticket for participant:", participant.name)

    # ✔ Create folders
    pdf_folder = os.path.join(
        settings.MEDIA_ROOT,
        f"Events/{participant.event.id}_{participant.event.event_name.replace(' ', '_')}/pdf_tickets",
    )
    os.makedirs(pdf_folder, exist_ok=True)

    # ✔ Sanitize file name
    sanitized_name = re.sub(r"\s+", "_", participant.name.strip())
    sanitized_email = participant.email.replace("@", "_").replace(".", "_")
<<<<<<< HEAD
    pdf_filename = f"{sanitized_name}_{sanitized_email}_ticket.pdf"
    pdf_path = os.path.join(pdf_folder, pdf_filename)

    # Create temporary directory for Gotenberg files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
=======

    pdf_filename = f"{participant.name}_{sanitized_email}_ticket.pdf"

    pdf_path = os.path.join(pdf_folder, pdf_filename)

    # ✅ Fix QR Code Path for PDF
    qr_image_path = participant.qr_code.url  # This should now return a valid media URL
>>>>>>> d510049 (File Logic Ready)

        # ✔ Prepare asset paths
        qr_image_path = participant.qr_code.path if participant.qr_code else None
        logo_path = (
            participant.event.company.logo.path
            if participant.event.company.logo
            else None
        )
        event_img_path = (
            participant.event.image.path if participant.event.image else None
        )

        # Copy assets to temporary directory with simple names
        assets_to_copy = []

        if qr_image_path and os.path.exists(qr_image_path):
            qr_temp_path = temp_path / "qr_code.png"
            shutil.copy2(qr_image_path, qr_temp_path)
            assets_to_copy.append(qr_temp_path)

        if logo_path and os.path.exists(logo_path):
            logo_temp_path = temp_path / "company_logo.png"
            shutil.copy2(logo_path, logo_temp_path)
            assets_to_copy.append(logo_temp_path)

        if event_img_path and os.path.exists(event_img_path):
            event_temp_path = temp_path / "event_image.png"
            shutil.copy2(event_img_path, event_temp_path)
            assets_to_copy.append(event_temp_path)

        # Copy CSS file
        css_source = os.path.join(
            settings.BASE_DIR, "core", "static", "css", "ticket_style.css"
        )
        css_temp_path = temp_path / "ticket_style.css"
        if os.path.exists(css_source):
            shutil.copy2(css_source, css_temp_path)
            assets_to_copy.append(css_temp_path)

        # Format date and time
        event_date = (
            participant.event.event_date.strftime("%B %d, %Y")
            if participant.event.event_date
            else "TBD"
        )

        #Format time range using start_time and end_time
        if participant.event.start_time and participant.event.end_time:
            start_time_str = participant.event.start_time.strftime("%I %p").lower()
            end_time_str = participant.event.end_time.strftime("%I %p").lower()
            event_time = f"{start_time_str} - {end_time_str}"
        elif participant.event.start_time:
            event_time = participant.event.start_time.strftime("%I %p").lower()
        else:
            event_time = "TBD"

        # ✔ Render HTML with dynamic content
        html_content = render_to_string(
            "ticket_gotenberg.html",
            {
                "participant": participant,
                "event_date": event_date,
                "event_time": event_time,
                "qr_image_exists": qr_image_path and os.path.exists(qr_image_path),
                "logo_exists": logo_path and os.path.exists(logo_path),
                "event_image_exists": event_img_path and os.path.exists(event_img_path),
            },
        )

        # Save HTML to temporary file
        html_temp_path = temp_path / "ticket.html"
        with open(html_temp_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # ✔ Generate PDF with Gotenberg
        try:
            with GotenbergClient("http://gotenberg:3000") as client:
                print("Gotenberg client initialized")
                with client.chromium.html_to_pdf() as route:
                    response = (
                        route.index(html_temp_path)
                        .resources(assets_to_copy)
                        .pdf_format(PdfAFormat.A2b)
                        .run()
                    )
                    # Save to temporary file first
                    temp_pdf_path = temp_path / "output.pdf"
                    response.to_file(temp_pdf_path)

                    # Read the PDF content and save as Django File
                    with open(temp_pdf_path, "rb") as pdf_file:
                        pdf_content = ContentFile(pdf_file.read())
                        relative_pdf_path = f"Events/{participant.event.id}_{participant.event.event_name.replace(' ', '_')}/pdf_tickets/{pdf_filename}"
                        participant.pdf_ticket.save(
                            relative_pdf_path, pdf_content, save=False
                        )

                    return relative_pdf_path

        except Exception as e:
            print(f"Error generating PDF with Gotenberg: {str(e)}")
            raise


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
    map_link_html = (
        f"""
        🗺️ <a href="{event_info['map_link']}" target="_blank" style="color: #1a73e8; text-decoration: none;">
            View Location on Google Maps
        </a>
    """
        if event_info["map_link"]
        else "🗺️ map_link: Not Provided"
    )
    body = f"""
        <h4>Dear {participant_name},</h4>
        <p>Thank you for your booking! Please find your ticket(s) attached to this email.</p>

        <p><strong>Event Details:</strong></p>
        <p>📅 Event: {event_info['title']}</p>
        <p> 📍 Location: {event_info['location']}</p>
        {map_link_html}
        <p>🕒 Date & Time: {event_info['date']} at {event_info['starttime']} - {event_info['endtime']}</p>
        
        <h5>Important Information:</h5>
        <p>✅ Please bring this ticket (printed or digital) for entry.</p>
        <p>✅ Ensure your QR code or barcode is visible for scanning at the entrance.</p>
        <p>✅ Doors open at: {event_info['starttime']} - Arrive early to secure your spot.</p>
        <p>✅ For any inquiries, contact us at: {event_info['company_email']}</p>



<<<<<<< HEAD
        <p>We look forward to seeing you at the event! 🎉</p>
=======
    # ✅ Return correct relative path for saving in the model
    relative_pdf_path = f"Events/{participant.event.id}_{participant.event.event_name.replace(' ', '_')}/pdf_tickets/{pdf_filename}"
>>>>>>> d510049 (File Logic Ready)

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
    """Export participants list as PDF using Gotenberg."""
    from django.template.loader import render_to_string
    from gotenberg_client import GotenbergClient
    from gotenberg_client.options import PdfAFormat
    from django.http import HttpResponse
    from .models import Event
    import tempfile
    from pathlib import Path
    from django.utils import timezone
    import os
    import shutil
    from django.conf import settings

    try:
        event = Event.objects.get(id=event_id)
        participants = event.participant_set.all().order_by("name")

        # Get unique custom fields from all participants
        custom_fields = set()
        for participant in participants:
            if participant.submitted_data:
                custom_fields.update(participant.submitted_data.keys())
        custom_fields = sorted(list(custom_fields))

        # Create temporary directory for Gotenberg files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            assets_to_copy = []

            # Copy company logo if exists
            if event.company and event.company.logo:
                try:
                    # Get the logo file from storage and fix path separators
                    logo_storage_path = event.company.logo.name.replace("\\", "/")

                    # Create destination path as a Path object
                    logo_dest = temp_path / "company_logo.png"

                    print(f"Logo storage path: {logo_storage_path}")
                    print(f"Logo destination: {logo_dest}")

                    # Try to read the file using Django's storage API
                    with default_storage.open(logo_storage_path, "rb") as src:
                        with open(logo_dest, "wb") as dst:
                            dst.write(src.read())

                    print(f"Logo file copied successfully to {logo_dest}")
                    assets_to_copy.append(logo_dest)

                except Exception as e:
                    print(f"Error handling company logo: {str(e)}")
                    print(
                        f"Logo path details - name: {event.company.logo.name}, path: {event.company.logo.path}"
                    )
                    # Continue without the logo if there's an error

            # Render HTML template
            html_content = render_to_string(
                "participants_list_pdf.html",
                {
                    "event": event,
                    "participants": participants,
                    "custom_fields": custom_fields,
                    "now": timezone.now(),
                    "logo_exists": bool(
                        assets_to_copy
                    ),  # Only true if logo was successfully copied
                },
            )

            # Save HTML to temporary file
            html_temp_path = temp_path / "participants_list.html"
            with open(html_temp_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            # Generate PDF with Gotenberg
            try:
                with GotenbergClient("http://gotenberg:3000") as client:
                    with client.chromium.html_to_pdf() as route:
                        # Ensure all paths are Path objects
                        response = (
                            route.index(html_temp_path)
                            .resources(
                                [
                                    Path(str(p)) if isinstance(p, str) else p
                                    for p in assets_to_copy
                                ]
                            )
                            .pdf_format(PdfAFormat.A2b)
                            .run()
                        )

                        # Create HTTP response
                        http_response = HttpResponse(
                            response.content, content_type="application/pdf"
                        )
                        http_response["Content-Disposition"] = (
                            f'attachment; filename="{event.event_name}_participants.pdf"'
                        )
                        return http_response

            except Exception as e:
                print(f"Error generating PDF with Gotenberg: {str(e)}")
                raise

    except Event.DoesNotExist:
        raise ValueError(f"Event with id {event_id} does not exist")


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
    from django.conf import settings

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
        # Fallback to settings - check for SITE_URL first, then ALLOWED_HOSTS
        base_url = getattr(settings, "SITE_URL", None)
        if not base_url:
            # Try to get from ALLOWED_HOSTS if SITE_URL is not set
            allowed_hosts = getattr(settings, "ALLOWED_HOSTS", [])
            if allowed_hosts and allowed_hosts != ["*"]:
                # Use the first non-wildcard host
                for host in allowed_hosts:
                    if host != "*" and not host.startswith("."):
                        # Check if it's HTTPS or HTTP based on CSRF_TRUSTED_ORIGINS
                        csrf_origins = getattr(settings, "CSRF_TRUSTED_ORIGINS", [])
                        protocol = (
                            "https"
                            if any(host in origin for origin in csrf_origins)
                            else "http"
                        )
                        base_url = f"{protocol}://{host}"
                        break
                else:
                    base_url = "http://127.0.0.1:8000"
            else:
                base_url = "http://127.0.0.1:8000"

        base_url = base_url.rstrip("/")

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


# def generate_certificate_for_participant(event, participant):
#     """
#     Generate certificate for a single participant using the proven working logic.
#     Extracted from generate_participant_certificate view to be reusable.
#     Returns (success: bool, message: str)
#     """
#     import tempfile
#     import os
#     import pypdf
#     from django.core.files.base import ContentFile
#     import logging

#     logger = logging.getLogger(__name__)

#     try:
#         print(f"=== CERTIFICATE GENERATION FOR {participant.name} ===")

#         if not event.certificate:
#             return False, "No certificate template found for this event."

#         file_extension = os.path.splitext(event.certificate.name)[1].lower()
#         if file_extension != ".pdf":
#             return False, "Certificate template must be a PDF file."

#         # Prepare form data to fill
#         form_data = {
#             "participant_name": participant.name,
#             "event_name": event.event_name,
#             "event_date": (
#                 event.event_date.strftime("%d %B %Y") if event.event_date else ""
#             ),
#             "company_name": event.company.name if event.company else "",
#         }

#         # Save the template PDF to a temporary file
#         with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_input:
#             with event.certificate.open("rb") as f:
#                 temp_input.write(f.read())
#             temp_input_path = temp_input.name

#         # Read the PDF template (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
#         reader = pypdf.PdfReader(temp_input_path)

#         # Check if PDF has pages (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
#         if len(reader.pages) == 0:
#             raise Exception(
#                 "The PDF file has no pages. This might be due to a failed DOCX to PDF conversion or a corrupted file."
#             )

#         print(f"PDF has {len(reader.pages)} page(s)")
#         writer = pypdf.PdfWriter()
#         writer.add_page(reader.pages[0])

#         # Check if the PDF has form fields (AcroForm) (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
#         has_form_fields = False
#         try:
#             form_fields = reader.get_fields()
#             if form_fields:
#                 has_form_fields = True
#                 print("PDF has form fields (via get_fields):", form_fields.keys())
#         except:
#             pass

#         if not has_form_fields:
#             # Check for AcroForm in a different way (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
#             try:
#                 if "/AcroForm" in reader.trailer["/Root"]:
#                     has_form_fields = True
#                     print("PDF has AcroForm - using form field filling")
#             except:
#                 pass

#         if has_form_fields:
#             # Try to fill form fields (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
#             try:
#                 writer.update_page_form_field_values(writer.pages[0], form_data)
#                 print("Successfully filled form fields")
#             except Exception as form_error:
#                 print(f"Form field filling failed: {form_error}")
#                 has_form_fields = False

#         if not has_form_fields:
#             print("PDF does not have fillable form fields")
#             # Try text-based replacement using PyMuPDF if available (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
#             try:
#                 import fitz  # PyMuPDF
#                 from django.conf import settings


#                 # Use PyMuPDF for text replacement
#                 doc = fitz.open(temp_input_path)
#                 replacements_made = 0

#                 font_path = getattr(settings, "PDF_REPLACEMENT_FONT", None)
#                 if not font_path or not os.path.exists(font_path):
#                     raise RuntimeError(f"PDF replacement font file not found: {font_path}")
#                 # returns an internal font name like "F1"
#                 embedded_fontname = doc.insert_font(file=font_path, fontname="DejaVuSans")

#                 # Define placeholder patterns to search for (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
#                 placeholder_patterns = {
#                     "participant_name": [
#                         "{{participant_name}}",
#                         "{{ participant_name }}",
#                         "{participant_name}",
#                         "{ participant_name }",
#                         "[participant_name]",
#                         "[ participant_name ]",
#                         "__PARTICIPANT_NAME__",
#                         "_PARTICIPANT_NAME_",
#                     ],
#                     "event_name": [
#                         "{{event_name}}",
#                         "{{ event_name }}",
#                         "{event_name}",
#                         "{ event_name }",
#                         "[event_name]",
#                         "[ event_name ]",
#                         "__EVENT_NAME__",
#                         "_EVENT_NAME_",
#                     ],
#                     "event_date": [
#                         "{{event_date}}",
#                         "{{ event_date }}",
#                         "{event_date}",
#                         "{ event_date }",
#                         "[event_date]",
#                         "[ event_date ]",
#                         "__EVENT_DATE__",
#                         "_EVENT_DATE_",
#                     ],
#                     "company_name": [
#                         "{{company_name}}",
#                         "{{ company_name }}",
#                         "{company_name}",
#                         "{ company_name }",
#                         "[company_name]",
#                         "[ company_name ]",
#                         "__COMPANY_NAME__",
#                         "_COMPANY_NAME_",
#                     ],
#                 }

#                 for page_num in range(len(doc)):
#                     page = doc[page_num]

#                     # Store replacement info for styled insertion after redaction
#                     styled_replacements = []

#                     # Replace placeholders (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
#                     for field_name, patterns in placeholder_patterns.items():
#                         if field_name in form_data and form_data[field_name]:
#                             for pattern in patterns:
#                                 # Search and replace text
#                                 text_instances = page.search_for(pattern)
#                                 for inst in text_instances:
#                                     # Get the original text properties to preserve styling
#                                     try:
#                                         # Get text details from the location
#                                         blocks = page.get_text("dict", clip=inst)

#                                         # Try to extract font information from the original text
#                                         font_name = "DejaVuSans"  # Default font
#                                         font_size = 12  # Default size
#                                         font_flags = 0  # Default flags
#                                         color = (0, 0, 0)  # Default black

#                                         if blocks and "blocks" in blocks:
#                                             for block in blocks["blocks"]:
#                                                 if "lines" in block:
#                                                     for line in block["lines"]:
#                                                         if "spans" in line:
#                                                             for span in line["spans"]:
#                                                                 span_text = span.get(
#                                                                     "text", ""
#                                                                 ).lower()
#                                                                 if (
#                                                                     pattern.lower()
#                                                                     in span_text
#                                                                 ):
#                                                                     font_name = (
#                                                                         span.get(
#                                                                             "font",
#                                                                             "DejaVuSans",
#                                                                         )
#                                                                     )
#                                                                     font_size = (
#                                                                         span.get(
#                                                                             "size", 12
#                                                                         )
#                                                                     )
#                                                                     font_flags = (
#                                                                         span.get(
#                                                                             "flags", 0
#                                                                         )
#                                                                     )
#                                                                     color = span.get(
#                                                                         "color", 0
#                                                                     )

#                                                                     # Handle color conversion
#                                                                     if isinstance(
#                                                                         color, int
#                                                                     ):
#                                                                         # Convert integer color to RGB tuple
#                                                                         if (
#                                                                             color != 0
#                                                                         ):  # Only convert if not default
#                                                                             color = (
#                                                                                 (
#                                                                                     color
#                                                                                     >> 16
#                                                                                 )
#                                                                                 & 255,
#                                                                                 (
#                                                                                     color
#                                                                                     >> 8
#                                                                                 )
#                                                                                 & 255,
#                                                                                 color
#                                                                                 & 255,
#                                                                             )
#                                                                             color = tuple(
#                                                                                 c
#                                                                                 / 255.0
#                                                                                 for c in color
#                                                                             )
#                                                                         else:
#                                                                             color = (
#                                                                                 0,
#                                                                                 0,
#                                                                                 0,
#                                                                             )  # Default black
#                                                                     elif isinstance(
#                                                                         color,
#                                                                         (list, tuple),
#                                                                     ):
#                                                                         # Already a tuple/list, normalize to 0-1 range
#                                                                         color = tuple(
#                                                                             (
#                                                                                 c
#                                                                                 / 255.0
#                                                                                 if c > 1
#                                                                                 else c
#                                                                             )
#                                                                             for c in color
#                                                                         )
#                                                                     break

#                                         # Calculate text position for replacement
#                                         replacement_text = form_data[field_name]

#                                         # Calculate center position
#                                         center_x = (inst.x0 + inst.x1) / 2
#                                         center_y = (inst.y0 + inst.y1) / 2

#                                         # Calculate starting position for left alignment
#                                         original_width = inst.x1 - inst.x0
#                                         estimated_char_width = font_size * 0.6
#                                         estimated_text_width = (
#                                             len(replacement_text) * estimated_char_width
#                                         )

#                                         if estimated_text_width < original_width:
#                                             text_x = (
#                                                 inst.x0
#                                                 + (
#                                                     original_width
#                                                     - estimated_text_width
#                                                 )
#                                                 / 2
#                                             )
#                                         else:
#                                             text_x = inst.x0

#                                         text_y = center_y
#                                         print("-----I am Here-----")
#                                         print(replacement_text)

#                                         styled_replacements.append(
#                                             {
#                                                 "position": fitz.Point(text_x, text_y),
#                                                 "text": replacement_text,
#                                                 "font": font_name,
#                                                 "size": font_size,
#                                                 "color": color,
#                                                 "fontname": embedded_fontname,
#                                             }
#                                         )

#                                         # Add redaction annotation to remove original text
#                                         page.add_redact_annot(inst, "")
#                                         replacements_made += 1

#                                     except Exception as e:
#                                         print(f"Error processing text replacement: {e}")
#                                         # Fallback with basic replacement
#                                         replacement_text = form_data[field_name]
#                                         center_x = (inst.x0 + inst.x1) / 2
#                                         center_y = (inst.y0 + inst.y1) / 2

#                                         # Calculate starting position for left alignment
#                                         original_width = inst.x1 - inst.x0
#                                         estimated_char_width = (
#                                             12 * 0.6
#                                         )  # Default font size
#                                         estimated_text_width = (
#                                             len(replacement_text) * estimated_char_width
#                                         )

#                                         if estimated_text_width < original_width:
#                                             text_x = (
#                                                 inst.x0
#                                                 + (
#                                                     original_width
#                                                     - estimated_text_width
#                                                 )
#                                                 / 2
#                                             )
#                                         else:
#                                             text_x = inst.x0

#                                         text_y = center_y

#                                         styled_replacements.append(
#                                             {
#                                                 "position": fitz.Point(text_x, text_y),
#                                                 "text": replacement_text,
#                                                 "font": "helv",
#                                                 "size": 12,
#                                                 "color": (0, 0, 0),
#                                                 "fontname": embedded_fontname,
#                                             }
#                                         )

#                                         page.add_redact_annot(inst, "")
#                                         replacements_made += 1

#                 # Apply all redactions first (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
#                 for page_num in range(len(doc)):
#                     page = doc[page_num]
#                     page.apply_redactions()

#                 # Then insert all the styled text replacements (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
#                 for page_num in range(len(doc)):
#                     page = doc[page_num]
#                     for replacement in styled_replacements:
#                         try:
#                             page.insert_text(
#                                 replacement["position"],
#                                 replacement["text"],
#                                 fontsize=replacement["size"],
#                                 color=replacement["color"],
#                                 fontname=embedded_fontname,
#                             )
#                         except Exception as insert_error:
#                             print(f"Error inserting styled text: {insert_error}")
#                             # Try basic insertion
#                             try:
#                                 page.insert_text(
#                                     replacement["position"], replacement["text"]
#                                 )
#                             except Exception as basic_error:
#                                 print(
#                                     f"Basic text insertion also failed: {basic_error}"
#                                 )

#                 # Save the modified document if we made replacements (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
#                 if replacements_made > 0:
#                     print(f"Made {replacements_made} text replacements")
#                     # Save to a new temporary file
#                     with tempfile.NamedTemporaryFile(
#                         delete=False, suffix=".pdf"
#                     ) as temp_modified:
#                         temp_modified_path = temp_modified.name

#                     # Save the modified document
#                     doc.save(temp_modified_path, garbage=4, deflate=True)
#                     doc.close()

#                     # Replace the original temp file with the modified one
#                     try:
#                         os.remove(temp_input_path)
#                         os.rename(temp_modified_path, temp_input_path)
#                     except Exception as file_error:
#                         print(f"Error replacing temp file: {file_error}")
#                         # If rename fails, use the new file
#                         temp_input_path = temp_modified_path

#                     # Re-read the PDF with pypdf
#                     reader = pypdf.PdfReader(temp_input_path)
#                     writer = pypdf.PdfWriter()
#                     writer.add_page(reader.pages[0])
#                 else:
#                     print("No text placeholders found for replacement")
#                     doc.close()

#             except ImportError:
#                 print("PyMuPDF not available - using basic PDF processing")
#             except Exception as text_error:
#                 print(f"Text replacement failed: {text_error}")

#         # Add metadata if available (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
#         if hasattr(reader, "metadata") and reader.metadata:
#             writer.add_metadata(reader.metadata)

#         # Save the final PDF (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
#         with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_output:
#             writer.write(temp_output)
#             temp_output_path = temp_output.name

#         # Read the final PDF content (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
#         with open(temp_output_path, "rb") as output_file:
#             filled_pdf = output_file.read()

#         # Save the certificate to the participant model (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
#         filename = f"certificate_{participant.name.replace(' ', '_')}.pdf"
#         participant.certificate.save(filename, ContentFile(filled_pdf), save=True)

#         # Clean up temporary files (EXACT SAME AS WORKING INDIVIDUAL FUNCTION)
#         try:
#             if os.path.exists(temp_input_path):
#                 os.remove(temp_input_path)
#         except Exception as cleanup_error:
#             print(f"Error cleaning up temp_input_path: {cleanup_error}")

#         try:
#             if os.path.exists(temp_output_path):
#                 os.remove(temp_output_path)
#         except Exception as cleanup_error:
#             print(f"Error cleaning up temp_output_path: {cleanup_error}")

#         print(f"Certificate generated successfully for {participant.name}")
#         return True, f"Certificate generated successfully for {participant.name}"

#     except Exception as e:
#         logger.exception("Failed to generate certificate")
#         error_msg = f"Failed to generate certificate for {participant.name}: {str(e)}"
#         print(error_msg)
#         return False, error_msg


def generate_certificate_for_participant(event, participant):
    """
    Generate a certificate PDF for a single participant.

    - If the template has AcroForm fields, try to fill with pypdf.
    - Otherwise, use PyMuPDF (fitz) text replacement with a Unicode TTF
      (registered per-page via page.insert_font), so Greek characters display.
    - Saves the generated PDF to participant.certificate (first page of template).

    Returns: (success: bool, message: str)
    """
    import os
    import tempfile
    import logging
    import pypdf

    from django.conf import settings
    from django.core.files.base import ContentFile

    logger = logging.getLogger(__name__)

    # Placeholder variants to search/replace
    placeholder_patterns = {
        "participant_name": [
            "{{participant_name}}", "{{ participant_name }}",
            "{participant_name}", "{ participant_name }",
            "[participant_name]", "[ participant_name ]",
            "__PARTICIPANT_NAME__", "_PARTICIPANT_NAME_",
        ],
        "event_name": [
            "{{event_name}}", "{{ event_name }}",
            "{event_name}", "{ event_name }",
            "[event_name]", "[ event_name ]",
            "__EVENT_NAME__", "_EVENT_NAME_",
        ],
        "event_date": [
            "{{event_date}}", "{{ event_date }}",
            "{event_date}", "{ event_date }",
            "[event_date]", "[ event_date ]",
            "__EVENT_DATE__", "_EVENT_DATE_",
        ],
        "company_name": [
            "{{company_name}}", "{{ company_name }}",
            "{company_name}", "{ company_name }",
            "[company_name]", "[ company_name ]",
            "__COMPANY_NAME__", "_COMPANY_NAME_",
        ],
    }

    try:
        # --- Basic checks
        if not event.certificate:
            return False, "No certificate template found for this event."

        file_extension = os.path.splitext(event.certificate.name)[1].lower()
        if file_extension != ".pdf":
            return False, "Certificate template must be a PDF file."

        # --- form data
        form_data = {
            "participant_name": (getattr(participant, "name", "") or "").strip(),
            "event_name": (getattr(event, "event_name", "") or "").strip(),
            "event_date": (
                event.event_date.strftime("%d %B %Y")
                if getattr(event, "event_date", None) else ""
            ),
            "company_name": (
                event.company.name if getattr(event, "company", None) else ""
            ),
        }

        # --- copy template to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_input:
            with event.certificate.open("rb") as fsrc:
                temp_input.write(fsrc.read())
            temp_input_path = temp_input.name

        # --- read with pypdf
        reader = pypdf.PdfReader(temp_input_path)
        if len(reader.pages) == 0:
            raise Exception("Template PDF has no pages (possibly corrupted).")

        writer = pypdf.PdfWriter()
        writer.add_page(reader.pages[0])  # keep original behavior: only first page

        # --- detect AcroForm fields
        has_form_fields = False
        try:
            fields = reader.get_fields()
            has_form_fields = bool(fields)
        except Exception:
            pass
        if not has_form_fields:
            try:
                has_form_fields = "/AcroForm" in reader.trailer.get("/Root", {})
            except Exception:
                has_form_fields = False

        # --- attempt pypdf form fill
        if has_form_fields:
            try:
                writer.update_page_form_field_values(writer.pages[0], form_data)
            except Exception as form_err:
                logger.warning("Form fill failed, fallback to text replacement: %s", form_err)
                has_form_fields = False

        # --- PyMuPDF text replacement path (older fitz API compatible)
        if not has_form_fields:
            try:
                import fitz  # PyMuPDF

                doc = fitz.open(temp_input_path)
                replacements_made = 0

                # Resolve a usable TTF path (system or project)
                system_font = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
                default_project_font = os.path.join(
                    settings.BASE_DIR, "core", "static", "fonts", "DejaVuSans.ttf"
                )
                cfg_font = getattr(settings, "PDF_REPLACEMENT_FONT", default_project_font)

                if os.path.exists(system_font):
                    font_path = system_font
                elif os.path.exists(cfg_font):
                    font_path = cfg_font
                else:
                    raise RuntimeError(
                        "DejaVuSans.ttf not found in system or project. "
                        "Install 'fonts-dejavu-core' or provide a TTF at core/static/fonts/DejaVuSans.ttf"
                    )

                # We'll measure text width with a Font object (works on old PyMuPDF)
                font_obj = fitz.Font(fontfile=font_path)

                # Collect replacements PER PAGE: store FINAL position (computed now)
                page_replacements = {i: [] for i in range(len(doc))}

                # 1) search placeholders and queue replacement info (compute true center using measured width)
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    for field_name, patterns in placeholder_patterns.items():
                        value = (form_data.get(field_name) or "").strip()
                        if not value:
                            continue

                        for pattern in patterns:
                            rects = page.search_for(pattern)
                            for inst in rects:
                                # infer style if possible
                                font_size = 12
                                color = (0.0, 0.0, 0.0)  # RGB (0..1)
                                try:
                                    blocks = page.get_text("dict", clip=inst)
                                    if blocks and "blocks" in blocks:
                                        found = False
                                        for block in blocks["blocks"]:
                                            for line in block.get("lines", []):
                                                for span in line.get("spans", []):
                                                    if pattern.lower() in span.get("text", "").lower():
                                                        fs = span.get("size", 12)
                                                        font_size = int(round(fs)) if fs else 12
                                                        col = span.get("color", 0)
                                                        if isinstance(col, int):
                                                            if col != 0:
                                                                r = ((col >> 16) & 255) / 255.0
                                                                g = ((col >> 8) & 255) / 255.0
                                                                b = (col & 255) / 255.0
                                                                color = (r, g, b)
                                                        elif isinstance(col, (list, tuple)):
                                                            color = tuple(
                                                                c if c <= 1 else c / 255.0
                                                                for c in col[:3]
                                                            )
                                                        found = True
                                                        break
                                                if found: break
                                            if found: break
                                except Exception:
                                    pass

                                # --- TRUE CENTER using measured width ---
                                rect_width = inst.x1 - inst.x0
                                text_width = font_obj.text_length(value, font_size)
                                text_x = inst.x0 + (rect_width - text_width) / 2
                                # baseline y: keep prior visual (mid-rect); adjust if needed
                                text_y = (inst.y0 + inst.y1) / 2

                                # redact original placeholder and queue draw (store FINAL pos)
                                page.add_redact_annot(inst, "")
                                page_replacements[page_num].append({
                                    "pos": fitz.Point(text_x, text_y),
                                    "text": value,
                                    "fontsize": font_size,
                                    "color": color,  # tuple of 0..1 floats
                                })
                                replacements_made += 1

                # 2) apply all redactions
                for i in range(len(doc)):
                    doc[i].apply_redactions()

                # 3) draw text: register font on each page, then use that font name
                #    On older PyMuPDF: page.insert_font(fontname=..., fontfile=..., encoding=0)
                #    Then page.insert_text(..., fontname="FDejaVu", encoding=0)
                for i, items in page_replacements.items():
                    if not items:
                        continue
                    page = doc[i]
                    try:
                        page.insert_font(fontname="FDejaVu", fontfile=font_path, encoding=0)
                    except Exception as e:
                        raise RuntimeError(f"Unable to register font on page {i}: {e}")

                    for r in items:
                        page.insert_text(
                            r["pos"],
                            r["text"],
                            fontsize=r["fontsize"],
                            color=r["color"],
                            fontname="FDejaVu",
                            encoding=0,        # ensure Unicode handling
                        )

                # 4) save back to temp_input_path so we can re-read with pypdf
                if replacements_made > 0:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_modified:
                        temp_modified_path = temp_modified.name
                    doc.save(temp_modified_path, garbage=4, deflate=True)
                    doc.close()

                    # swap files
                    try:
                        os.remove(temp_input_path)
                        os.rename(temp_modified_path, temp_input_path)
                    except Exception:
                        temp_input_path = temp_modified_path

                    # re-read and keep first page
                    reader = pypdf.PdfReader(temp_input_path)
                    writer = pypdf.PdfWriter()
                    writer.add_page(reader.pages[0])
                else:
                    doc.close()

            except Exception as text_err:
                logger.exception("Text replacement failed")
                return False, f"Text replacement failed: {text_err}"

        # --- Preserve metadata when possible
        try:
            if getattr(reader, "metadata", None):
                writer.add_metadata(reader.metadata)
        except Exception:
            pass

        # --- write final output to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_output:
            writer.write(temp_output)
            temp_output_path = temp_output.name

        # --- save to model
        with open(temp_output_path, "rb") as outf:
            filled_pdf = outf.read()

        safe_name = (form_data["participant_name"] or "participant").replace(" ", "_")
        filename = f"certificate_{safe_name}.pdf"
        participant.certificate.save(filename, ContentFile(filled_pdf), save=True)

        # --- cleanup
        try:
            if os.path.exists(temp_input_path):
                os.remove(temp_input_path)
        except Exception:
            pass
        try:
            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)
        except Exception:
            pass

        return True, f"Certificate generated successfully for {participant.name}"

    except Exception as e:
        logger.exception("Failed to generate certificate")
        who = getattr(participant, "name", "participant")
        return False, f"Failed to generate certificate for {who}: {e}"





def generate_paidticket_pdf(paid_ticket):
    """Generate a PDF ticket for a PaidTicket using Gotenberg client with HTML template."""
    import os, re, shutil, tempfile
    from pathlib import Path
    from django.conf import settings
    from django.core.files.base import ContentFile
    from django.template.loader import render_to_string

    print("Generating PDF ticket for paid ticket UUID:", paid_ticket.uuid)

    event = paid_ticket.order.event
    participant = paid_ticket.participant

    # ✔ Create folders
    pdf_folder = os.path.join(
        settings.MEDIA_ROOT,
        f"Events/{event.id}_{event.event_name.replace(' ', '_')}/paid_tickets",
    )
    os.makedirs(pdf_folder, exist_ok=True)

    # ✔ Sanitize file name
    pdf_filename = f"paidticket_{paid_ticket.uuid}_ticket.pdf"
    pdf_path = os.path.join(pdf_folder, pdf_filename)

    # Create temporary directory for Gotenberg files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # ✔ Prepare asset paths
        qr_image_path = paid_ticket.qr_code.path if paid_ticket.qr_code else None
        logo_path = event.company.logo.path if event.company.logo else None
        event_img_path = event.image.path if event.image else None

        # Copy assets to temporary directory with simple names
        assets_to_copy = []

        if qr_image_path and os.path.exists(qr_image_path):
            qr_temp_path = temp_path / "qr_code.png"
            shutil.copy2(qr_image_path, qr_temp_path)
            assets_to_copy.append(qr_temp_path)

        if logo_path and os.path.exists(logo_path):
            logo_temp_path = temp_path / "company_logo.png"
            shutil.copy2(logo_path, logo_temp_path)
            assets_to_copy.append(logo_temp_path)

        if event_img_path and os.path.exists(event_img_path):
            event_temp_path = temp_path / "event_image.png"
            shutil.copy2(event_img_path, event_temp_path)
            assets_to_copy.append(event_temp_path)

        # Copy CSS file
        css_source = os.path.join(
            settings.BASE_DIR, "core", "static", "css", "ticket_style.css"
        )
        css_temp_path = temp_path / "ticket_style.css"
        if os.path.exists(css_source):
            shutil.copy2(css_source, css_temp_path)
            assets_to_copy.append(css_temp_path)

        # Format date and time
        event_date = (
            event.event_date.strftime("%B %d, %Y") if event.event_date else "TBD"
        )

        # Format time range using start_time and end_time
        if event.start_time and event.end_time:
            start_time_str = event.start_time.strftime("%I %p").lower()
            end_time_str = event.end_time.strftime("%I %p").lower()
            event_time = f"{start_time_str} - {end_time_str}"
        elif event.start_time:
            event_time = event.start_time.strftime("%I %p").lower()
        else:
            event_time = "TBD"

        # ✔ Render HTML with dynamic content
        html_content = render_to_string(
            "ticket_gotenberg.html",
            {
                "ticket_id": paid_ticket.uuid,
                "participant": participant,
                "event": event,
                "ticket_type": paid_ticket.ticket_type,
                "event_date": event_date,
                "event_time": event_time,
                "qr_image_exists": qr_image_path and os.path.exists(qr_image_path),
                "logo_exists": logo_path and os.path.exists(logo_path),
                "event_image_exists": event_img_path and os.path.exists(event_img_path),
            },
        )

        # Save HTML to temporary file
        html_temp_path = temp_path / "ticket.html"
        with open(html_temp_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # ✔ Generate PDF with Gotenberg
        try:
            with GotenbergClient("http://gotenberg:3000") as client:
                print("Gotenberg client initialized")
                with client.chromium.html_to_pdf() as route:
                    response = (
                        route.index(html_temp_path)
                        .resources(assets_to_copy)
                        .pdf_format(PdfAFormat.A2b)
                        .run()
                    )
                    # Save to temporary file first
                    temp_pdf_path = temp_path / "output.pdf"
                    response.to_file(temp_pdf_path)

                    # Read the PDF content and save as Django File
                    with open(temp_pdf_path, "rb") as pdf_file:
                        pdf_content = ContentFile(pdf_file.read())
                        relative_pdf_path = f"Events/{event.id}_{event.event_name.replace(' ', '_')}/paid_tickets/{pdf_filename}"
                        paid_ticket.pdf_ticket.save(
                            relative_pdf_path, pdf_content, save=False
                        )

                    return relative_pdf_path

        except Exception as e:
            print(f"Error generating PDF with Gotenberg: {str(e)}")
            raise