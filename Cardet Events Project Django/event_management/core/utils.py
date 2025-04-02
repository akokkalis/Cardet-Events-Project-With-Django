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


def generate_pdf_ticket(participant, qr_code_path):
    """Generate a PDF ticket using an HTML template."""

    site_url = f"{settings.SITE_URL}"
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

    font_path = os.path.join(settings.BASE_DIR, "core", "fonts", "DejaVuSans.ttf")
    print("MY FONT URL:", font_path)
    company_logo_url = (
        f"{site_url}{participant.event.company.logo.url}"
        if participant.event.company.logo
        else None
    )

    event_image_url = (
        f"{site_url}{participant.event.image.url}" if participant.event.image else None
    )

    # ✅ Generate HTML from template
    html_content = render_to_string(
        "pdf_template.html",
        {
            "participant": participant,
            "qr_image_path": qr_image_path[1:],  # Convert to relative path
            "company_logo_url": company_logo_url,
            "event_image_url": event_image_url,
            "font_path": font_path.replace("\\", "/"),
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

        # ✅ Write Table Headers
        writer.writerow(["#", "Name", "Email", "Phone", "Signature Image"])

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

            writer.writerow(
                [
                    i,
                    participant.name,
                    participant.email,
                    participant.phone or "-",
                    signature_path,
                ]
            )

    # ✅ Return CSV as Response
    with open(csv_path, "rb") as f:
        response = HttpResponse(f, content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="{event.event_name}_participants.csv"'
        )
        return response


def export_participants_pdf(event_id, re):
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

    # ✅ Table Headers
    y = 440
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(30, y, "#")
    pdf.drawString(60, y, "Name")
    pdf.drawString(200, y, "Email")
    pdf.drawString(350, y, "Phone")
    pdf.drawString(500, y, "Signature")

    # ✅ Fetch all participants
    y -= 20
    pdf.setFont("Helvetica", 10)
    participants = event.participant_set.prefetch_related("attendance_set").all()

    for i, participant in enumerate(participants, start=1):
        pdf.drawString(30, y, str(i))
        pdf.drawString(60, y, participant.name)
        pdf.drawString(200, y, participant.email)
        pdf.drawString(350, y, participant.phone or "-")

        attendance = participant.attendance_set.first()

        # ✅ Embed Signature Image
        if attendance and attendance.signature_file:
            signature_path = os.path.join(
                settings.MEDIA_ROOT, attendance.signature_file.name
            )
            if os.path.exists(signature_path):
                img = ImageReader(signature_path)
                pdf.drawImage(
                    img, 500, y - 10, width=50, height=20
                )  # Adjust dimensions
            else:
                pdf.drawString(500, y, "Missing")
        else:
            pdf.drawString(500, y, "Not Signed")

        y -= 20  # Move to next row

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
