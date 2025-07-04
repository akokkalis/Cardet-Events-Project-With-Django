from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError
from .models import (
    Event,
    Participant,
    Attendance,
    Status,
    Company,
    Staff,
    EventCustomField,
    EventEmail,
    RSVPResponse,
    EmailConfiguration,
)
from .forms import (
    EventForm,
    ParticipantForm,
    EventCustomFieldForm,
    CompanyForm,
    EventEmailForm,
    EmailConfigurationForm,
)
from django.core.paginator import Paginator
from django.db.models import Q, Case, When, Value, IntegerField, F, Window
from django.db.models.functions import RowNumber
from django.utils.timezone import now
from django.http import JsonResponse, FileResponse, HttpResponse
import base64
from django.core.files.base import ContentFile
import os
from django.conf import settings
import zipfile
from datetime import date
from django.views.decorators.csrf import csrf_exempt
import json
from django.core.mail import EmailMessage, get_connection
from django.utils.html import strip_tags
import threading
from .utils import (
    email_body,
    export_participants_pdf,
    export_participants_csv,
    generate_ics_file,
)
from .signals import send_rsvp_email
from django_ratelimit.decorators import ratelimit

from django.utils.decorators import method_decorator
import re

# from pdfjinja import PdfJinja
import tempfile
import logging
import pypdf
import concurrent.futures
from core.tasks import test_hello


def login_view(request):
    """Handles staff login and ensures only staff members can access the system."""

    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)
        print(user)
        if user:
            # ✅ Check if the user is a Staff member
            if Staff.objects.filter(user=user).exists():
                login(request, user)
                return redirect("event_list")  # Redirect to event list after login
            else:
                messages.error(request, "Access Denied! You are not a staff member.")
                return redirect("login")  # Redirect back to login page
        else:
            messages.error(request, "Invalid username or password.")

        messages.error(request, "Invalid username or password.")
        return redirect("login")  # Redirect if authentication fails

    return render(request, "login.html")


def logout_view(request):
    """Logs out the user."""
    logout(request)
    return redirect("login")


@login_required
def event_list(request):
    """Displays a list of events sorted by priority, date, and status."""

    today = date.today()
    statuses = Status.objects.all()
    companies = Company.objects.all()

    # Extract unique event years dynamically
    event_years = Event.objects.dates("event_date", "year", order="DESC")

    # Priority Mapping (from Status Model)
    priority_mapping = {status.id: status.priority for status in statuses}

    # Sorting: Priority (lower is better), then by date
    events = (
        Event.objects.select_related("status")
        .annotate(
            priority=Case(
                *[
                    When(status_id=status.id, then=Value(priority_mapping[status.id]))
                    for status in statuses
                ],
                default=Value(99),  # Default lowest priority if status not found
                output_field=IntegerField(),
            )
        )
        .order_by("priority", "event_date")
    )

    return render(
        request,
        "events.html",
        {
            "events": events,
            "statuses": statuses,
            "companies": companies,
            "event_years": event_years,
        },
    )


@login_required
def filter_events(request):
    """Filter events dynamically via AJAX and maintain sorting order."""
    company_id = request.GET.get("company")
    status_id = request.GET.get("status")
    event_date = request.GET.get("date")
    event_month = request.GET.get("month")
    event_year = request.GET.get("year")
    print("asjdjasdhj")
    statuses = Status.objects.all()

    # Priority Mapping (Admin Configurable)
    priority_mapping = {status.id: status.priority for status in statuses}

    # Start filtering
    events = Event.objects.all()

    if company_id:
        events = events.filter(company_id=company_id)

    if status_id:
        events = events.filter(status_id=status_id)

    if event_date:
        events = events.filter(event_date=event_date)

    if event_year:
        events = events.filter(event_date__year=event_year)

    if event_month:
        events = events.filter(event_date__month=event_month)

    # Apply Sorting (Priority First, Then Date)
    events = events.annotate(
        priority=Case(
            *[
                When(status_id=status.id, then=Value(priority_mapping[status.id]))
                for status in statuses
            ],
            default=Value(99),
            output_field=IntegerField(),
        )
    ).order_by("priority", "event_date")

    event_list = [
        {
            "id": event.id,
            "event_name": event.event_name,
            "event_date": event.event_date.strftime("%Y-%m-%d"),
            "start_time": (
                event.start_time.strftime("%H:%M") if event.start_time else "N/A"
            ),
            "end_time": event.end_time.strftime("%H:%M") if event.end_time else "N/A",
            "company": event.company.name,
            "status": event.status.name if event.status else "No Status",
            "status_color": event.status.color if event.status else "#cccccc",
            "image_url": event.image.url if event.image else None,
            "participant_count": event.participant_set.count(),
        }
        for event in events
    ]

    return JsonResponse({"events": event_list})


@login_required
def event_create(request):
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save()
            return redirect(
                "event_custom_fields", event_id=event.id
            )  # Redirect to custom fields page
    else:
        form = EventForm()

    return render(request, "event_form.html", {"form": form})


@login_required
def event_edit(request, event_id):
    """Edit an existing event."""
    event = get_object_or_404(Event, id=event_id)

    next_url = request.GET.get("next", None)  # Get the `next` parameter from URL

    if request.method == "POST":
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            # Redirect back to where user came from, if provided
            if next_url:
                return redirect(next_url)
            return redirect("event_list")  # Fallback to event list
    else:
        form = EventForm(instance=event)

    return render(request, "event_edit.html", {"form": form, "event": event})


@login_required
def event_delete(request, event_id):

    event = get_object_or_404(Event, id=event_id)
    event.delete()
    messages.success(request, "Event deleted successfully!")
    return redirect("event_list")


def get_missing_email_templates(event):
    """Check which email templates are missing for an event"""
    # Get existing templates for this event
    existing_templates = EventEmail.objects.filter(event=event).values_list(
        "reason", flat=True
    )

    # Define all possible template types
    all_template_types = [
        ("registration", "Registration Email"),
        ("approval", "Approval Email"),
        ("rejection", "Rejection Email"),
        ("rsvp", "RSVP Request Email"),
    ]

    # Find missing templates
    missing_templates = []
    for reason, display_name in all_template_types:
        if reason not in existing_templates:
            missing_templates.append({"reason": reason, "display_name": display_name})

    return missing_templates


@login_required
def event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    participants = Participant.objects.filter(event=event).order_by("name")
    present_participants = Attendance.objects.filter(
        event=event, present=True
    ).values_list("participant", flat=True)
    not_present_participants = participants.exclude(id__in=present_participants)

    # Check for missing email templates
    missing_email_templates = get_missing_email_templates(event)
    import json

    missing_email_templates_json = json.dumps(missing_email_templates)

    # Check specifically if RSVP template is missing
    rsvp_template_missing = any(
        template["reason"] == "rsvp" for template in missing_email_templates
    )

    for participant in participants:
        participant.attendance = Attendance.objects.filter(
            participant=participant, event=event
        ).first()

        # Get RSVP response for this participant
        rsvp_response = RSVPResponse.objects.filter(
            participant=participant, event=event
        ).first()

        if rsvp_response:
            participant.rsvp_response = rsvp_response.response
            participant.rsvp_response_display = {
                "attend": "✅ Will Attend",
                "cant_make_it": "❌ Can't Make It",
                "maybe": "🤔 Maybe",
            }.get(rsvp_response.response, "Unknown")
            participant.has_rsvp_response = True
        else:
            participant.rsvp_response = None
            participant.rsvp_response_display = "No Response"
            participant.has_rsvp_response = False

        # Add file information to submitted_data if it exists
        if participant.submitted_data:
            import json
            from core.models import ParticipantCustomFieldFile

            # Get custom field files for this participant
            custom_files = ParticipantCustomFieldFile.objects.filter(
                participant=participant
            )

            # Create a copy of submitted_data to modify
            custom_data = participant.submitted_data.copy()

            # Add file IDs to submitted_data for files
            for file_obj in custom_files:
                if file_obj.field_label in custom_data:
                    # Replace filename with file info including download URL
                    custom_data[file_obj.field_label] = {
                        "is_file": True,
                        "filename": file_obj.file.name.split("/")[-1],
                        "file_id": file_obj.id,
                    }

            # Convert to JSON string for the template
            try:
                participant.custom_data_json = json.dumps(custom_data)
            except Exception as e:
                print(
                    f"Error serializing custom data for participant {participant.name}: {e}"
                )
                participant.custom_data_json = "{}"
        else:
            participant.custom_data_json = "{}"

    context = {
        "event": event,
        "participants": participants,
        "present_participants": participants.filter(id__in=present_participants),
        "not_present_participants": not_present_participants,
        "missing_email_templates": missing_email_templates,
        "missing_email_templates_json": missing_email_templates_json,
        "rsvp_template_missing": rsvp_template_missing,
    }

    return render(request, "event_detail.html", context)


@login_required
def scan_qr(request, event_id):
    """Serves the scanner page for an event and displays attendance lists."""

    event = get_object_or_404(Event, id=event_id)

    # Ensure only events with ticket scanning enabled allow scanning
    if not event.tickets:
        messages.error(request, "This event does not support QR code scanning.")
        return redirect("event_detail", event_id=event.id)

    # Get all participants for the event
    all_participants = Participant.objects.filter(event=event)

    # Get participants who have checked in
    present_participants = Attendance.objects.filter(
        event=event, present=True
    ).values_list("participant_id", flat=True)

    # Filter participants into Present and Not Present groups
    present_list = all_participants.filter(id__in=present_participants)
    not_present_list = all_participants.exclude(id__in=present_participants)

    context = {
        "event": event,
        "present_participants": present_list,
        "not_present_participants": not_present_list,
    }

    return render(request, "scan_qr.html", context)


@login_required
def mark_attendance(request):
    """Handles QR code scan and marks attendance."""

    if request.method == "POST":
        event_id = request.POST.get("event_id")
        participant_id = request.POST.get("participant_id")

        try:
            event = get_object_or_404(Event, id=event_id)
            participant = get_object_or_404(Participant, id=participant_id, event=event)
        except (Event.DoesNotExist, Participant.DoesNotExist):
            return JsonResponse(
                {"status": "error", "message": "Invalid QR code."}, status=400
            )

        # Check if attendance already exists
        attendance, created = Attendance.objects.get_or_create(
            participant=participant, event=event
        )
        if attendance.present:
            return JsonResponse(
                {
                    "status": "warning",
                    "message": f"{participant.name} is already checked in!",
                }
            )

        attendance.present = True
        attendance.timestamp = now()
        attendance.save()

        # ✅ If the event requires a signature, redirect to the signature page
        if event.signatures:
            return JsonResponse(
                {
                    "status": "signature_required",
                    "redirect_url": f"/sign_signature/{event.id}/{participant.id}/",
                }
            )
        total_present = Attendance.objects.filter(event=event, present=True).count()
        total_registered = Participant.objects.filter(event=event).count()
        not_present = total_registered - total_present

        return JsonResponse(
            {
                "status": "success",
                "message": f"{participant.name} checked in successfully.",
                "participant_name": participant.name,
                "present_count": total_present,
                "not_present_count": not_present,
            }
        )

    return JsonResponse({"status": "error", "message": "Invalid request."}, status=400)


@login_required
def signature_path(instance, filename):
    """Returns the correct path to store signatures inside the event folder."""
    return f"Events/{instance.event.id}_{instance.event.event_name.replace(' ', '_')}/signatures/{instance.participant.name}_{instance.participant.email.replace('@', '_').replace('.', '_')}_signature.png"


@login_required
def sign_signature(request, event_id, participant_id):
    """Serves the signature page and saves the signature."""

    event = get_object_or_404(Event, id=event_id)
    participant = get_object_or_404(Participant, id=participant_id, event=event)

    if request.method == "GET":
        # ✅ Serve the signature page when accessed via GET request
        return render(
            request, "signature.html", {"event": event, "participant": participant}
        )

    if request.method == "POST":
        signature_data = request.POST.get("signature")

        if not signature_data:
            return JsonResponse(
                {"status": "error", "message": "No signature data received."},
                status=400,
            )

        # Convert the Base64 signature data to an image file
        format, imgstr = signature_data.split(";base64,")
        ext = format.split("/")[-1]
        filename = f"{participant.name}_{participant.email.replace('@', '_').replace('.', '_')}_signature.{ext}"

        # ✅ Ensure the signature is saved inside the correct event folder inside `MEDIA_ROOT`
        signature_folder = os.path.join(
            settings.MEDIA_ROOT,
            f"Events/{event.id}_{event.event_name.replace(' ', '_')}/signatures",
        )
        os.makedirs(signature_folder, exist_ok=True)  # Ensure the folder exists

        signature_file_path = os.path.join(signature_folder, filename)

        # Convert base64 image data to Django ContentFile
        signature_file = ContentFile(base64.b64decode(imgstr), name=filename)

        # Get or create attendance record
        attendance, created = Attendance.objects.get_or_create(
            participant=participant, event=event
        )

        # Save the signature file inside the correct path
        attendance.signature_file.save(
            f"Events/{event.id}_{event.event_name.replace(' ', '_')}/signatures/{filename}",
            signature_file,
            save=True,
        )
        attendance.present = True  # Mark as present when signing
        attendance.save()

        return JsonResponse(
            {"status": "success", "message": "Signature saved successfully!"}
        )

    return JsonResponse(
        {"status": "error", "message": "Invalid request method."}, status=400
    )


@login_required
def export_zip(request, event_id):
    """Generates a ZIP file containing all PDF tickets and signatures for an event."""
    event = get_object_or_404(Event, id=event_id)

    # Define the event folder path
    event_folder = os.path.join(
        "media", f"Events/{event.id}_{event.event_name.replace(' ', '_')}"
    )
    zip_filename = f"{event.event_name.replace(' ', '_')}_Export.zip"

    # Create a ZIP file
    zip_path = os.path.join("media", zip_filename)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Add PDF Tickets if available
        pdf_folder = os.path.join(event_folder, "pdf_tickets")
        if os.path.exists(pdf_folder):
            for root, _, files in os.walk(pdf_folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.relpath(file_path, "media"))

        # Add Signatures if available
        signature_folder = os.path.join(event_folder, "signatures")
        if os.path.exists(signature_folder):
            for root, _, files in os.walk(signature_folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.relpath(file_path, "media"))

        # Add Custom Field Files if available
        custom_files_folder = os.path.join(event_folder, "custom_field_files")
        if os.path.exists(custom_files_folder):
            for root, _, files in os.walk(custom_files_folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.relpath(file_path, "media"))

        # Add Event Image if available
        if event.image:
            event_image_folder = os.path.join(event_folder, "event_image")
            if os.path.exists(event_image_folder):
                for root, _, files in os.walk(event_image_folder):
                    for file in files:
                        file_path = os.path.join(root, file)
                        zipf.write(file_path, os.path.relpath(file_path, "media"))

        # Add QR Codes if available
        qr_codes_folder = os.path.join(event_folder, "qr_codes")
        if os.path.exists(qr_codes_folder):
            for root, _, files in os.walk(qr_codes_folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.relpath(file_path, "media"))

        # Add Certificates if available
        certificates_folder = os.path.join(event_folder, "certificates")
        if os.path.exists(certificates_folder):
            for root, _, files in os.walk(certificates_folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.relpath(file_path, "media"))

    # Serve the ZIP file for download
    zip_file = open(zip_path, "rb")
    response = FileResponse(zip_file, as_attachment=True, filename=zip_filename)

    return response


@csrf_exempt  # 🚨 Allows API calls from external sources (remove in production if CSRF protection needed)
def register_participant_api(request):
    """API endpoint to register a participant via POST request from an external WordPress site."""

    if request.method == "POST":
        try:
            data = json.loads(request.body)  # Parse JSON data from request

            event_id = data.get("event_id")
            name = data.get("name")
            email = data.get("email")
            phone = data.get("phone", "")

            if not event_id or not name or not email:
                return JsonResponse(
                    {"status": "error", "message": "Missing required fields."},
                    status=400,
                )

            # Get the event
            event = get_object_or_404(Event, id=event_id)

            # Check if participant already exists
            participant, created = Participant.objects.get_or_create(
                event=event, email=email, defaults={"name": name, "phone": phone}
            )

            if not created:
                return JsonResponse(
                    {"status": "error", "message": "Participant already registered."},
                    status=409,
                )

            # # ✅ Generate QR Code if tickets are required
            # if event.tickets:
            #     participant.generate_qr_code()

            # # ✅ Generate PDF Ticket if tickets are required
            # if event.tickets:
            #     from .utils import generate_pdf_ticket  # Import your PDF function

            #     pdf_path = generate_pdf_ticket(participant, participant.qr_code.path)
            #     participant.pdf_ticket = pdf_path
            #     participant.save()

            return JsonResponse(
                {
                    "status": "success",
                    "message": "Participant registered successfully.",
                },
                status=201,
            )

        except json.JSONDecodeError:
            return JsonResponse(
                {"status": "error", "message": "Invalid JSON format."}, status=400
            )

    return JsonResponse(
        {"status": "error", "message": "Invalid request method."}, status=405
    )


def send_ticket_email_view(request):
    """Handles sending ticket email manually via AJAX request using the same logic from signals.py"""

    if request.method == "POST":
        participant_id = request.POST.get("participant_id")
        participant = get_object_or_404(Participant, id=participant_id)

        # ✅ Ensure event requires tickets and participant has a ticket
        if not participant.event.tickets or not participant.pdf_ticket:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "This event does not require tickets or no ticket found.",
                },
                status=400,
            )

        # ✅ Get company email configuration
        email_config = getattr(participant.event.company, "email_config", None)
        if not email_config:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "No email configuration found for this company.",
                },
                status=400,
            )

        # ✅ Email subject & event information
        subject = f"Your Ticket for {participant.event.event_name}"
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
        )  # Remove HTML tags for plaintext fallback

        # ✅ Get PDF Ticket Path
        pdf_path = participant.pdf_ticket.path if participant.pdf_ticket else None

        # ✅ Create SMTP connection (same as signals.py)
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

                # ✅ Attach the ticket if available
                if pdf_path and os.path.exists(pdf_path):
                    email.attach_file(pdf_path)

                email.send()
                print(f"✅ Ticket email sent to {participant.email}")

            except Exception as e:
                print(f"❌ Error sending email to {participant.email}: {e}")

        # ✅ Run email function in a separate thread (non-blocking)
        email_thread = threading.Thread(target=send_email)
        email_thread.start()

        return JsonResponse(
            {"status": "success", "message": "Ticket sent successfully!"}, status=200
        )

    return JsonResponse(
        {"status": "error", "message": "Invalid request method."}, status=400
    )


def export_participants_csv_view(request, event_id):
    """View to export participants as CSV."""
    return export_participants_csv(event_id)


def export_participants_pdf_view(request, event_id):
    """View to export participants as PDF."""
    return export_participants_pdf(event_id)


# 💥 Allow 5 POSTs per minute per IP


@ratelimit(key="ip")  # 5 requests per minute
def public_register(request, event_uuid):
    event = get_object_or_404(Event, uuid=event_uuid)
    custom_fields = EventCustomField.objects.filter(event=event).order_by("order")

    # Options are now handled automatically by the options_list property in the model

    # If rate limit exceeded, show error page
    if getattr(request, "limited", False):
        return render(request, "rate_limit_exceeded.html", {"event": event})

    # Only allow if event status is "on-going"
    if not event.status or event.status.name.lower() != "on-going":
        return render(request, "registration_closed.html", {"event": event})

    if request.method == "POST":
        form = ParticipantForm(request.POST, request.FILES)

        # Collect custom field data
        custom_data = {}
        for field in custom_fields:
            if field.field_type == "multiselect":
                # Handle multiple values for multiselect
                field_values = request.POST.getlist(f"custom_field_{field.id}")
                if field.required and not field_values:
                    messages.error(request, f"{field.label} is required.")
                    return render(
                        request,
                        "public_register.html",
                        {"form": form, "event": event, "custom_fields": custom_fields},
                    )
                custom_data[field.label] = field_values
            elif field.field_type == "checkbox":
                # Handle checkbox - value is "true" when checked, None when unchecked
                field_value = request.POST.get(f"custom_field_{field.id}")
                if field.required and not field_value:
                    messages.error(request, f"{field.label} is required.")
                    return render(
                        request,
                        "public_register.html",
                        {"form": form, "event": event, "custom_fields": custom_fields},
                    )
                custom_data[field.label] = field_value == "true"
            elif field.field_type == "range":
                # Handle range input - ensure it's a valid number
                field_value = request.POST.get(f"custom_field_{field.id}")
                if field.required and not field_value:
                    messages.error(request, f"{field.label} is required.")
                    return render(
                        request,
                        "public_register.html",
                        {"form": form, "event": event, "custom_fields": custom_fields},
                    )
                try:
                    # Convert to integer and validate range
                    if field_value:
                        range_value = int(field_value)
                        min_val, max_val = (
                            field.range_values
                        )  # Get custom min/max values
                        if range_value < min_val or range_value > max_val:
                            messages.error(
                                request,
                                f"{field.label} must be between {min_val} and {max_val}.",
                            )
                            return render(
                                request,
                                "public_register.html",
                                {
                                    "form": form,
                                    "event": event,
                                    "custom_fields": custom_fields,
                                },
                            )
                        custom_data[field.label] = range_value
                    else:
                        custom_data[field.label] = field_value
                except ValueError:
                    messages.error(request, f"{field.label} must be a valid number.")
                    return render(
                        request,
                        "public_register.html",
                        {"form": form, "event": event, "custom_fields": custom_fields},
                    )
            elif field.field_type in ["date", "time", "datetime"]:
                # Handle date/time field types
                field_value = request.POST.get(f"custom_field_{field.id}")
                if field.required and not field_value:
                    messages.error(request, f"{field.label} is required.")
                    return render(
                        request,
                        "public_register.html",
                        {"form": form, "event": event, "custom_fields": custom_fields},
                    )

                # For date/time fields, we'll store the value as-is since HTML5 inputs provide ISO format
                # The browser handles validation for invalid date/time formats
                custom_data[field.label] = field_value
            elif field.field_type == "file":
                # Handle file uploads
                uploaded_file = request.FILES.get(f"custom_field_{field.id}")
                if field.required and not uploaded_file:
                    messages.error(request, f"{field.label} is required.")
                    return render(
                        request,
                        "public_register.html",
                        {"form": form, "event": event, "custom_fields": custom_fields},
                    )
                # Store the file name for now, actual file will be saved after participant is created
                custom_data[field.label] = uploaded_file.name if uploaded_file else None
            else:
                # Handle other field types (text, textarea, number, email, select)
                field_value = request.POST.get(f"custom_field_{field.id}")
                if field.required and not field_value:
                    messages.error(request, f"{field.label} is required.")
                    return render(
                        request,
                        "public_register.html",
                        {"form": form, "event": event, "custom_fields": custom_fields},
                    )
                custom_data[field.label] = field_value

        if form.is_valid():
            email = form.cleaned_data["email"]

            # Check standard email uniqueness
            if Participant.objects.filter(event=event, email=email).exists():
                messages.error(request, "This email is already registered.")
                return render(
                    request,
                    "public_register.html",
                    {"form": form, "event": event, "custom_fields": custom_fields},
                )

            # Save participant
            participant = form.save(commit=False)
            participant.event = event

            # Save custom field data in participant's submitted_data field
            if custom_fields.exists():
                # Add participant data to custom data
                registration_data = {
                    **custom_data,
                }
                participant.submitted_data = registration_data

            participant.save()

            # Save uploaded files for custom fields
            for field in custom_fields:
                if field.field_type == "file":
                    uploaded_file = request.FILES.get(f"custom_field_{field.id}")
                    if uploaded_file:
                        from core.models import ParticipantCustomFieldFile

                        ParticipantCustomFieldFile.objects.create(
                            participant=participant,
                            field_label=field.label,
                            file=uploaded_file,
                        )

            messages.success(request, "✅ Registered successfully!")
            return redirect("public_register", event_uuid=event.uuid)
    else:
        form = ParticipantForm()

    return render(
        request,
        "public_register.html",
        {"form": form, "event": event, "custom_fields": custom_fields},
    )


def download_ics_file(request, event_uuid):
    """Download the .ics file for an event identified by UUID."""
    event = Event.objects.get(uuid=event_uuid)
    ics_file_path = generate_ics_file(event, request)

    with open(ics_file_path, "rb") as ics_file:
        response = HttpResponse(ics_file.read(), content_type="text/calendar")
        response["Content-Disposition"] = (
            f'attachment; filename="{event.event_name}.ics"'
        )
        return response


@login_required
def register_participant_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == "POST":
        form = ParticipantForm(request.POST, request.FILES, event=event)
        if form.is_valid():
            try:
                participant = form.save(commit=False)
                participant.event = event

                # Handling custom fields
                custom_data = {}
                for key, value in form.cleaned_data.items():
                    if key.startswith("custom_field_"):
                        field_id = int(key.split("_")[-1])
                        field_model = EventCustomField.objects.get(id=field_id)

                        if field_model.field_type == "file" and value:
                            # For file fields, store the filename in custom_data
                            custom_data[field_model.label] = value.name
                        else:
                            custom_data[field_model.label] = value

                participant.submitted_data = custom_data
                participant.save()

                # Save uploaded files for custom fields
                for key, value in form.cleaned_data.items():
                    if key.startswith("custom_field_") and value:
                        field_id = int(key.split("_")[-1])
                        field_model = EventCustomField.objects.get(id=field_id)

                        if field_model.field_type == "file":
                            from core.models import ParticipantCustomFieldFile

                            ParticipantCustomFieldFile.objects.create(
                                participant=participant,
                                field_label=field_model.label,
                                file=value,
                            )
                # form.save_m2m() is not needed unless ParticipantForm has M2M fields itself

                messages.success(
                    request, f"Participant {participant.name} added successfully."
                )
                return redirect("event_detail", event_id=event.id)

            except IntegrityError:
                # Handle duplicate email error
                email = form.cleaned_data.get("email", "")
                messages.error(
                    request,
                    f"❌ This email address ({email}) is already registered for this event. Please use a different email address.",
                )
                # The form will be re-displayed with the error message
    else:
        form = ParticipantForm(event=event)

    return render(request, "register_participant.html", {"form": form, "event": event})


def event_custom_fields(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    fields = EventCustomField.objects.filter(event=event).order_by("order")

    if request.method == "POST":
        form = EventCustomFieldForm(request.POST, event=event)
        if form.is_valid():
            custom_field = form.save(commit=False)
            custom_field.event = event
            custom_field.save()
            messages.success(request, "Custom field added successfully!")
            return redirect("event_custom_fields", event_id=event.id)
    else:
        form = EventCustomFieldForm(event=event)

    return render(
        request,
        "event_custom_fields.html",
        {"event": event, "form": form, "existing_fields": fields},
    )


def delete_custom_field(request, event_id, field_id):
    if request.method == "POST":
        field = get_object_or_404(EventCustomField, id=field_id, event_id=event_id)
        field.delete()
        messages.success(request, "Custom field deleted successfully!")
    return redirect("event_custom_fields", event_id=event_id)


@login_required
def update_field_order(request, event_id):
    """AJAX endpoint to update custom field order via drag and drop."""
    if request.method == "POST":
        try:
            import json
            from django.db import transaction

            data = json.loads(request.body)
            updates = data.get("updates", [])

            event = get_object_or_404(Event, id=event_id)

            # Use database transaction to ensure consistency
            with transaction.atomic():
                from django.db.models import F

                # Simply update all fields to their new positions
                # This is much simpler and avoids complex logic
                for update in updates:
                    field_id = int(update["id"])
                    new_order = int(update["order"])

                    # First, temporarily set all fields to a high number to avoid conflicts
                    EventCustomField.objects.filter(id=field_id, event=event).update(
                        order=9999 + field_id
                    )

                # Now set all fields to their final positions
                for update in updates:
                    field_id = int(update["id"])
                    new_order = int(update["order"])

                    EventCustomField.objects.filter(id=field_id, event=event).update(
                        order=new_order
                    )

            return JsonResponse({"success": True})

        except Exception as e:
            print(e)
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
def download_custom_field_file(request, file_id):
    """View to serve custom field files"""
    try:
        from core.models import ParticipantCustomFieldFile

        custom_file = get_object_or_404(ParticipantCustomFieldFile, id=file_id)

        # Check if user has access to this event (basic security)
        if (
            hasattr(request.user, "staff")
            and request.user.staff.company != custom_file.participant.event.company
        ):
            return HttpResponse("Unauthorized", status=403)

        response = HttpResponse(
            custom_file.file.read(), content_type="application/octet-stream"
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{custom_file.file.name.split("/")[-1]}"'
        )
        return response

    except Exception as e:
        return HttpResponse(f"File not found: {str(e)}", status=404)


@login_required
def company_list(request):
    """Display list of companies"""
    companies = Company.objects.all().order_by("name")

    context = {
        "companies": companies,
    }

    return render(request, "companies.html", context)


@login_required
def company_create(request):
    """Create a new company"""
    if request.method == "POST":
        form = CompanyForm(request.POST, request.FILES)
        if form.is_valid():
            company = form.save()
            messages.success(request, f"Company '{company.name}' created successfully!")
            return redirect("company_list")
    else:
        form = CompanyForm()

    return render(
        request, "company_form.html", {"form": form, "title": "Add New Company"}
    )


@login_required
def company_edit(request, company_id):
    """Edit an existing company"""
    company = get_object_or_404(Company, id=company_id)

    if request.method == "POST":
        form = CompanyForm(request.POST, request.FILES, instance=company)
        if form.is_valid():
            company = form.save()
            messages.success(request, f"Company '{company.name}' updated successfully!")
            return redirect("company_list")
    else:
        form = CompanyForm(instance=company)

    return render(
        request,
        "company_form.html",
        {"form": form, "title": f"Edit {company.name}", "company": company},
    )


@login_required
def company_detail(request, company_id):
    """View company details"""
    company = get_object_or_404(Company, id=company_id)
    events = Event.objects.filter(company=company).order_by("-event_date")

    # Check if email configuration exists
    try:
        email_config = EmailConfiguration.objects.get(company=company)
        has_email_config = True
    except EmailConfiguration.DoesNotExist:
        has_email_config = False

        # Add RSVP statistics for each event
    events_with_rsvp_stats = []
    for event in events:
        total_participants = event.participant_set.count()
        total_rsvp_responses = RSVPResponse.objects.filter(event=event).count()

        # Check if event has RSVP template
        has_rsvp_template = EventEmail.objects.filter(
            event=event, reason="rsvp"
        ).exists()

        # Add the statistics to the event object
        event.rsvp_responses_count = total_rsvp_responses
        event.total_participants_count = total_participants
        event.has_rsvp_template = has_rsvp_template
        events_with_rsvp_stats.append(event)

    context = {
        "company": company,
        "events": events_with_rsvp_stats,
        "has_email_config": has_email_config,
    }

    return render(request, "company_detail.html", context)


@login_required
def help_view(request):
    return render(request, "help.html")


@login_required
def event_email_templates(request, event_id):
    """Display and manage email templates for a specific event"""
    event = get_object_or_404(Event, id=event_id)

    # Get all email templates for this event
    email_templates = EventEmail.objects.filter(event=event).order_by("reason")

    # Create a dictionary to track which reasons exist
    existing_reasons = {template.reason for template in email_templates}

    # Define all possible reasons and their display names
    all_reasons = [
        ("registration", "Registration Email"),
        ("approval", "Approval Email"),
        ("rejection", "Rejection Email"),
        ("rsvp", "RSVP Request Email"),
    ]

    # Find missing templates that can be created
    missing_templates = [
        (reason, display_name)
        for reason, display_name in all_reasons
        if reason not in existing_reasons
    ]

    context = {
        "event": event,
        "email_templates": email_templates,
        "missing_templates": missing_templates,
        "all_reasons": dict(all_reasons),  # For display purposes
    }

    return render(request, "event_email_templates.html", context)


@login_required
def add_email_template(request, event_id):
    """Add a new email template for a specific event"""
    event = get_object_or_404(Event, id=event_id)
    reason = request.GET.get("reason")

    # Validate that the reason is valid
    valid_reasons = ["registration", "approval", "rejection", "rsvp"]
    if reason not in valid_reasons:
        messages.error(request, "Invalid email template type.")
        return redirect("event_email_templates", event_id=event.id)

    # Check if template already exists
    if EventEmail.objects.filter(event=event, reason=reason).exists():
        messages.error(
            request, f'An email template for "{reason}" already exists for this event.'
        )
        return redirect("event_email_templates", event_id=event.id)

    if request.method == "POST":
        form = EventEmailForm(request.POST, event=event, initial_reason=reason)
        if form.is_valid():
            email_template = form.save(commit=False)
            email_template.event = event
            email_template.save()

            reason_display = dict(EventEmail.REASON_CHOICES)[reason]
            messages.success(
                request, f"{reason_display} email template created successfully!"
            )
            return redirect("event_email_templates", event_id=event.id)
    else:
        form = EventEmailForm(event=event, initial_reason=reason)

    reason_display = dict(EventEmail.REASON_CHOICES)[reason]
    context = {
        "event": event,
        "form": form,
        "reason": reason,
        "reason_display": reason_display,
        "is_edit": False,
    }

    return render(request, "email_template_form.html", context)


@login_required
def edit_email_template(request, event_id, template_id):
    """Edit an existing email template"""
    event = get_object_or_404(Event, id=event_id)
    template = get_object_or_404(EventEmail, id=template_id, event=event)

    if request.method == "POST":
        form = EventEmailForm(request.POST, instance=template, event=event)
        if form.is_valid():
            form.save()

            reason_display = dict(EventEmail.REASON_CHOICES)[template.reason]
            messages.success(
                request, f"{reason_display} email template updated successfully!"
            )
            return redirect("event_email_templates", event_id=event.id)
    else:
        form = EventEmailForm(instance=template, event=event)

    reason_display = dict(EventEmail.REASON_CHOICES)[template.reason]
    context = {
        "event": event,
        "form": form,
        "template": template,
        "reason_display": reason_display,
        "is_edit": True,
    }

    return render(request, "email_template_form.html", context)


@login_required
def delete_email_template(request, event_id, template_id):
    """Delete an email template"""
    event = get_object_or_404(Event, id=event_id)
    template = get_object_or_404(EventEmail, id=template_id, event=event)

    if request.method == "POST":
        reason_display = dict(EventEmail.REASON_CHOICES)[template.reason]
        template.delete()
        messages.success(
            request, f"{reason_display} email template deleted successfully!"
        )

    return redirect("event_email_templates", event_id=event.id)


@login_required
def approve_participant(request, event_id, participant_id):
    """Approve a participant and send approval and ticket emails if applicable."""
    event = get_object_or_404(Event, id=event_id)
    participant = get_object_or_404(Participant, id=participant_id, event=event)

    # Import here to avoid circular imports
    from .signals import handle_participant_approval

    if participant.approval_status != "approved":
        participant.approval_status = "approved"
        participant.save(update_fields=["approval_status"])

        # Handle approval emails and ticket sending
        handle_participant_approval(participant)

        if event.tickets:
            messages.success(
                request,
                f"✅ {participant.name} has been approved and notified via email. "
                f"Ticket generation is in progress and will be sent automatically.",
            )
        else:
            messages.success(
                request,
                f"✅ {participant.name} has been approved and notified via email.",
            )
    else:
        messages.info(request, f"{participant.name} is already approved.")

    return redirect("event_detail", event_id=event.id)


@login_required
def reject_participant(request, event_id, participant_id):
    """Reject a participant and send rejection email."""
    event = get_object_or_404(Event, id=event_id)
    participant = get_object_or_404(Participant, id=participant_id, event=event)

    # Import here to avoid circular imports
    from .signals import handle_participant_rejection

    if participant.approval_status != "rejected":
        participant.approval_status = "rejected"
        participant.save(update_fields=["approval_status"])

        # Handle rejection email
        handle_participant_rejection(participant)

        messages.success(
            request, f"❌ {participant.name} has been rejected and notified via email."
        )
    else:
        messages.info(request, f"{participant.name} is already rejected.")

    return redirect("event_detail", event_id=event.id)


@login_required
def set_participant_pending(request, event_id, participant_id):
    """Set a participant back to pending status."""
    event = get_object_or_404(Event, id=event_id)
    participant = get_object_or_404(Participant, id=participant_id, event=event)

    if participant.approval_status != "pending":
        participant.approval_status = "pending"
        participant.save(update_fields=["approval_status"])

        messages.success(
            request, f"🔄 {participant.name} has been set to pending status."
        )
    else:
        messages.info(request, f"{participant.name} is already pending.")

    return redirect("event_detail", event_id=event.id)


@login_required
def check_participant_status(request, event_id, participant_id):
    """AJAX endpoint to check participant PDF generation status."""
    try:
        event = get_object_or_404(Event, id=event_id)
        participant = get_object_or_404(Participant, id=participant_id, event=event)

        response_data = {
            "participant_id": participant.id,
            "approval_status": participant.approval_status,
            "has_pdf_ticket": bool(participant.pdf_ticket),
            "pdf_url": participant.pdf_ticket.url if participant.pdf_ticket else None,
            "status_badge_html": "",
            "pdf_download_html": "",
            "send_ticket_html": "",
        }

        # Generate status badge HTML
        if participant.approval_status == "approved":
            response_data[
                "status_badge_html"
            ] = """
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                    ✅ Approved
                </span>
            """
        elif participant.approval_status == "rejected":
            response_data[
                "status_badge_html"
            ] = """
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                    ❌ Rejected
                </span>
            """
        else:
            response_data[
                "status_badge_html"
            ] = """
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                    🟡 Pending
                </span>
            """

        # Generate PDF download HTML
        if participant.pdf_ticket:
            response_data[
                "pdf_download_html"
            ] = f"""
                <a href="{participant.pdf_ticket.url}" target="_blank" class="text-blue-500 underline">Download</a>
            """
            response_data[
                "send_ticket_html"
            ] = f"""
                <button class="send-ticket-btn btn btn-outline-blue" data-participant-id="{participant.id}">
                    Send Ticket
                </button>
            """
        else:
            # Check if the event requires tickets
            if event.tickets:
                if participant.approval_status == "approved":
                    response_data[
                        "pdf_download_html"
                    ] = """
                        <div class="flex items-center gap-2 text-orange-500 font-medium">
                            <div class="inline-block w-4 h-4 border-2 border-orange-500 border-t-transparent rounded-full animate-spin"></div>
                            <span>Generating...</span>
                        </div>
                    """
                    response_data[
                        "send_ticket_html"
                    ] = """
                        <div class="flex items-center gap-2 text-orange-500">
                            <div class="inline-block w-4 h-4 border-2 border-orange-500 border-t-transparent rounded-full animate-spin"></div>
                            <span>Generating...</span>
                        </div>
                    """
                else:
                    response_data[
                        "pdf_download_html"
                    ] = """
                        <span class="text-gray-500">No Ticket</span>
                    """
                    response_data[
                        "send_ticket_html"
                    ] = """
                        <span class="text-gray-500">No Ticket</span>
                    """
            else:
                # Event doesn't require tickets
                response_data[
                    "pdf_download_html"
                ] = """
                    <span class="text-gray-500">No Tickets Required</span>
                """
                response_data[
                    "send_ticket_html"
                ] = """
                    <span class="text-gray-500">No Tickets Required</span>
                """

        return JsonResponse(response_data)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=404)


@login_required
def company_email_settings(request, company_id):
    """Add or edit email settings for a company"""
    company = get_object_or_404(Company, id=company_id)

    try:
        email_config = EmailConfiguration.objects.get(company=company)
        is_editing = True
    except EmailConfiguration.DoesNotExist:
        email_config = None
        is_editing = False

    if request.method == "POST":
        form = EmailConfigurationForm(request.POST, instance=email_config)
        if form.is_valid():
            email_config = form.save(commit=False)
            email_config.company = company
            email_config.save()

            action = "updated" if is_editing else "added"
            messages.success(
                request, f"✅ Email settings {action} successfully for {company.name}!"
            )
            return redirect("company_detail", company_id=company.id)
    else:
        form = EmailConfigurationForm(instance=email_config)

    context = {
        "form": form,
        "company": company,
        "is_editing": is_editing,
    }

    return render(request, "company_email_settings.html", context)


# RSVP Views
def rsvp_response(request, event_uuid, participant_id, response):
    """Handle RSVP responses from email links"""
    try:
        event = get_object_or_404(Event, uuid=event_uuid)
        participant = get_object_or_404(Participant, id=participant_id, event=event)

        # Validate response
        valid_responses = ["attend", "cant_make_it", "maybe"]
        if response not in valid_responses:
            messages.error(request, "Invalid RSVP response.")
            return render(request, "rsvp_error.html", {"event": event})

        # Create or update RSVP response
        from django.utils import timezone

        rsvp, created = RSVPResponse.objects.update_or_create(
            participant=participant,
            event=event,
            defaults={
                "response": response,
                "notes": (
                    request.POST.get("notes", "") if request.method == "POST" else ""
                ),
                "response_date": timezone.now(),
            },
        )

        # Get display text for the response
        response_display = {
            "attend": "Attend",
            "cant_make_it": "Can't make it",
            "maybe": "Maybe",
        }[response]

        context = {
            "event": event,
            "participant": participant,
            "rsvp": rsvp,
            "response_display": response_display,
            "created": created,
        }

        return render(request, "rsvp_success.html", context)

    except Exception as e:
        return render(request, "rsvp_error.html", {"error": str(e)})


@csrf_exempt
def rsvp_response_with_notes(request, event_uuid, participant_id, response):
    """Handle RSVP responses with optional notes"""
    if request.method == "POST":
        try:
            event = get_object_or_404(Event, uuid=event_uuid)
            participant = get_object_or_404(Participant, id=participant_id, event=event)

            # Validate response
            valid_responses = ["attend", "cant_make_it", "maybe"]
            if response not in valid_responses:
                return JsonResponse({"error": "Invalid RSVP response."}, status=400)

            notes = request.POST.get("notes", "")

            # Create or update RSVP response
            rsvp, created = RSVPResponse.objects.update_or_create(
                participant=participant,
                event=event,
                defaults={
                    "response": response,
                    "notes": notes,
                    "response_date": timezone.now(),
                },
            )

            # Get display text for the response
            response_display = {
                "attend": "Attend",
                "cant_make_it": "Can't make it",
                "maybe": "Maybe",
            }[response]

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Thank you! Your RSVP has been recorded as '{response_display}'.",
                    "response": response,
                    "response_display": response_display,
                    "created": created,
                }
            )

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    # If GET request, show the RSVP form page
    try:
        event = get_object_or_404(Event, uuid=event_uuid)
        participant = get_object_or_404(Participant, id=participant_id, event=event)

        # Get existing RSVP if it exists
        existing_rsvp = RSVPResponse.objects.filter(
            participant=participant, event=event
        ).first()

        response_display = {
            "attend": "Attend",
            "cant_make_it": "Can't make it",
            "maybe": "Maybe",
        }[response]

        context = {
            "event": event,
            "participant": participant,
            "response": response,
            "response_display": response_display,
            "existing_rsvp": existing_rsvp,
        }

        return render(request, "rsvp_form.html", context)

    except Exception as e:
        return render(request, "rsvp_error.html", {"error": str(e)})


@login_required
def event_rsvp_summary(request, event_id):
    """View RSVP summary for an event"""
    event = get_object_or_404(Event, id=event_id)

    # Get RSVP statistics
    rsvp_responses = RSVPResponse.objects.filter(event=event)

    stats = {
        "attend": rsvp_responses.filter(response="attend").count(),
        "cant_make_it": rsvp_responses.filter(response="cant_make_it").count(),
        "maybe": rsvp_responses.filter(response="maybe").count(),
        "total_responses": rsvp_responses.count(),
        "total_participants": event.participant_set.count(),
    }

    # Calculate response rate
    if stats["total_participants"] > 0:
        stats["response_rate"] = (
            stats["total_responses"] / stats["total_participants"]
        ) * 100
    else:
        stats["response_rate"] = 0

    # Get detailed responses
    detailed_responses = rsvp_responses.select_related("participant").order_by(
        "-response_date"
    )

    context = {"event": event, "stats": stats, "detailed_responses": detailed_responses}

    return render(request, "event_rsvp_summary.html", context)


@login_required
def send_rsvp_email_participant_view(request, event_id, participant_id):
    """View to trigger sending an RSVP email to a single participant."""
    event = get_object_or_404(Event, id=event_id)
    participant = get_object_or_404(Participant, id=participant_id, event=event)

    # Check if an RSVP email template exists
    if not EventEmail.objects.filter(event=event, reason="rsvp").exists():
        messages.error(
            request,
            f"No RSVP email template found for this event. Please create one first.",
        )
        return redirect("event_detail", event_id=event.id)

    try:
        # Call the email sending function from signals.py
        send_rsvp_email(participant)
        messages.success(
            request, f"RSVP email sent successfully to {participant.name}."
        )
    except Exception as e:
        messages.error(
            request, f"Failed to send RSVP email to {participant.name}. Error: {e}"
        )

    return redirect("event_detail", event_id=event.id)


@login_required
def send_bulk_rsvp_emails(request, event_id):
    """Send RSVP emails to all approved participants who haven't responded yet"""
    if request.method != "POST":
        return JsonResponse({"error": "Only POST requests allowed"}, status=405)

    event = get_object_or_404(Event, id=event_id)

    # Check if RSVP template exists
    if not EventEmail.objects.filter(event=event, reason="rsvp").exists():
        return JsonResponse(
            {"error": "No RSVP email template found for this event."}, status=400
        )

    # Get approved participants who haven't responded to RSVP
    from .models import RSVPResponse, RSVPEmailLog

    responded_participants = RSVPResponse.objects.filter(event=event).values_list(
        "participant_id", flat=True
    )

    eligible_participants = Participant.objects.filter(
        event=event, approval_status="approved"
    ).exclude(id__in=responded_participants)

    if not eligible_participants.exists():
        return JsonResponse(
            {
                "error": "No eligible participants found. All approved participants have already responded."
            },
            status=400,
        )

    # Create email log entry
    email_log = RSVPEmailLog.objects.create(
        event=event,
        user=request.user,
        total_recipients=eligible_participants.count(),
        status="in_progress",
    )

    # Start background email sending
    import threading
    from .signals import send_rsvp_email
    from django.utils import timezone

    def send_emails_in_background():
        emails_sent = 0
        emails_failed = 0

        try:
            for participant in eligible_participants:
                try:
                    send_rsvp_email(participant)
                    emails_sent += 1
                except Exception as e:
                    emails_failed += 1
                    print(f"Failed to send RSVP email to {participant.email}: {e}")

            # Update log as completed
            email_log.emails_sent = emails_sent
            email_log.emails_failed = emails_failed
            email_log.status = "completed"
            email_log.completed_at = timezone.now()
            email_log.save()

        except Exception as e:
            # Update log as failed
            email_log.status = "failed"
            email_log.error_message = str(e)
            email_log.completed_at = timezone.now()
            email_log.save()

    # Start the background thread
    email_thread = threading.Thread(target=send_emails_in_background)
    email_thread.daemon = True
    email_thread.start()

    return JsonResponse(
        {
            "success": True,
            "message": f"Started sending RSVP emails to {eligible_participants.count()} participants.",
            "log_id": email_log.id,
            "total_recipients": eligible_participants.count(),
        }
    )


@login_required
def check_rsvp_email_status(request, log_id):
    """Check the status of a bulk RSVP email sending operation"""
    try:
        from .models import RSVPEmailLog

        email_log = get_object_or_404(RSVPEmailLog, id=log_id, user=request.user)

        return JsonResponse(
            {
                "status": email_log.status,
                "total_recipients": email_log.total_recipients,
                "emails_sent": email_log.emails_sent,
                "emails_failed": email_log.emails_failed,
                "started_at": email_log.started_at.strftime("%Y-%m-%d %H:%M:%S"),
                "completed_at": (
                    email_log.completed_at.strftime("%Y-%m-%d %H:%M:%S")
                    if email_log.completed_at
                    else None
                ),
                "error_message": email_log.error_message,
            }
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=404)


@login_required
def bulk_approve_participants(request, event_id):
    """Bulk approve/reject/set pending for multiple participants"""
    if request.method != "POST":
        return JsonResponse({"error": "Only POST requests allowed"}, status=405)

    try:
        event = get_object_or_404(Event, id=event_id)
        data = json.loads(request.body)
        participant_ids = data.get("participant_ids", [])
        action = data.get("action")  # 'approve', 'reject', or 'pending'

        if not participant_ids:
            return JsonResponse({"error": "No participants selected"}, status=400)

        if action not in ["approve", "reject", "pending"]:
            return JsonResponse({"error": "Invalid action"}, status=400)

        # Get participants
        participants = Participant.objects.filter(id__in=participant_ids, event=event)

        if not participants.exists():
            return JsonResponse({"error": "No valid participants found"}, status=400)

        # Update participants based on action
        status_mapping = {
            "approve": "approved",
            "reject": "rejected",
            "pending": "pending",
        }

        new_status = status_mapping[action]
        updated_count = 0

        # Import here to avoid circular imports
        from .signals import handle_participant_approval, handle_participant_rejection

        for participant in participants:
            if participant.approval_status != new_status:
                participant.approval_status = new_status
                participant.save(update_fields=["approval_status"])
                updated_count += 1

                # Handle email notifications for approval/rejection
                if action == "approve":
                    handle_participant_approval(participant)
                elif action == "reject":
                    handle_participant_rejection(participant)

        action_display = {
            "approve": "approved",
            "reject": "rejected",
            "pending": "set to pending",
        }

        return JsonResponse(
            {
                "success": True,
                "message": f"Successfully {action_display[action]} {updated_count} participants.",
                "updated_count": updated_count,
            }
        )

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def export_participant_template(request, event_id):
    """Export a CSV template for participant import with all required fields and custom fields"""
    event = get_object_or_404(Event, id=event_id)

    # Get all custom fields for this event
    custom_fields = EventCustomField.objects.filter(event=event).order_by("order")

    # Create response object
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="{event.event_name}_participant_template.csv"'
    )

    import csv

    writer = csv.writer(response)

    # Create header row with required fields and custom fields
    headers = [
        "name *REQUIRED*",
        "email *REQUIRED*",
        "phone",
    ]

    # Add custom fields to headers with required indicators
    for field in custom_fields:
        field_header = field.label
        if field.required:
            field_header += " *REQUIRED*"

        # Add field type and options info for clarity
        if field.field_type == "select" and field.options:
            field_header += f" (Options: {field.options})"
        elif field.field_type == "multiselect" and field.options:
            field_header += f" (Multi-select: {field.options})"
        elif field.field_type == "checkbox":
            field_header += " (true/false)"
        elif field.field_type == "range" and field.options:
            field_header += f" (Range: {field.options})"
        elif field.field_type == "file":
            field_header += " (File uploads not supported in CSV import)"

        headers.append(field_header)

    writer.writerow(headers)

    # Add example row with sample data
    example_row = ["John Doe", "john.doe@example.com", "+1234567890"]

    # Add example values for custom fields
    for field in custom_fields:
        if field.field_type == "text":
            example_row.append("Sample text")
        elif field.field_type == "textarea":
            example_row.append("Sample longer text")
        elif field.field_type == "number":
            example_row.append("123")
        elif field.field_type == "email":
            example_row.append("sample@example.com")
        elif field.field_type == "select":
            if field.options:
                example_row.append(field.options.split(",")[0].strip())
            else:
                example_row.append("Option1")
        elif field.field_type == "multiselect":
            if field.options:
                options = field.options.split(",")
                example_row.append(
                    f"{options[0].strip()}, {options[1].strip() if len(options) > 1 else options[0].strip()}"
                )
            else:
                example_row.append("Option1, Option2")
        elif field.field_type == "checkbox":
            example_row.append("true")
        elif field.field_type == "range":
            example_row.append("5")
        elif field.field_type == "date":
            example_row.append("2024-12-31")
        elif field.field_type == "time":
            example_row.append("14:30")
        elif field.field_type == "datetime":
            example_row.append("2024-12-31 14:30")
        elif field.field_type == "file":
            example_row.append("Not supported in CSV")
        else:
            example_row.append("Sample value")

    writer.writerow(example_row)

    # Add instruction rows
    writer.writerow([])  # Empty row
    writer.writerow(["INSTRUCTIONS:"])
    writer.writerow(["1. Fill in the participant data in the rows below"])
    writer.writerow(["2. Fields marked with *REQUIRED* must be filled"])
    writer.writerow(["3. Delete this instruction section before importing"])
    writer.writerow(
        [
            "4. All imported participants will have 'pending' status and require manual approval"
        ]
    )
    writer.writerow(["5. For multi-select fields, separate values with commas"])
    writer.writerow(["6. For checkbox fields, use: true or false"])
    writer.writerow(
        ["7. Date format: YYYY-MM-DD, Time format: HH:MM, DateTime: YYYY-MM-DD HH:MM"]
    )
    writer.writerow(["8. File uploads are not supported via CSV import"])
    writer.writerow([])  # Empty row
    writer.writerow(["START ENTERING DATA BELOW THIS LINE:"])
    writer.writerow([])  # Empty row for data entry

    return response


@login_required
def import_participants_csv(request, event_id):
    """Import participants from CSV file"""
    event = get_object_or_404(Event, id=event_id)
    print(event)

    if request.method == "POST":
        csv_file = request.FILES.get("csv_file")

        if not csv_file:
            error_msg = "Please select a CSV file to upload."
            messages.error(request, error_msg)
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"status": "error", "message": error_msg})
            return redirect("event_detail", event_id=event.id)

        if not csv_file.name.endswith(".csv"):
            error_msg = "Please upload a valid CSV file."
            messages.error(request, error_msg)
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"status": "error", "message": error_msg})
            return redirect("event_detail", event_id=event.id)

        try:
            import csv
            import io

            # Read CSV file
            file_data = csv_file.read().decode("utf-8")
            csv_data = csv.reader(io.StringIO(file_data))

            # Convert to list immediately to avoid consumption issues
            all_csv_rows = list(csv_data)
            if not all_csv_rows:
                messages.error(request, "CSV file is empty.")
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse(
                        {"status": "error", "message": "CSV file is empty."}
                    )
                return redirect("event_detail", event_id=event.id)

            # Get headers
            headers = all_csv_rows[0]
            data_rows = all_csv_rows[1:]  # All data rows

            # Clean headers (remove *REQUIRED* markers and extra info)
            clean_headers = []
            for header in headers:
                clean_header = header.split(" *REQUIRED*")[0].split(" (")[0].strip()
                clean_headers.append(clean_header)

            # Get custom fields for validation
            custom_fields = EventCustomField.objects.filter(event=event).order_by(
                "order"
            )
            custom_field_labels = [field.label for field in custom_fields]
            required_custom_fields = [
                field.label for field in custom_fields if field.required
            ]

            # Validate headers
            required_headers = ["name", "email"]
            missing_required = []
            for req_header in required_headers:
                if req_header not in clean_headers:
                    missing_required.append(req_header)

            if missing_required:
                error_msg = f'Missing required columns: {", ".join(missing_required)}'
                messages.error(request, error_msg)
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"status": "error", "message": error_msg})
                return redirect("event_detail", event_id=event.id)

            # Get total rows count
            total_rows = len(data_rows)

            if total_rows == 0:
                error_msg = "CSV file contains no data rows."
                messages.error(request, error_msg)
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"status": "error", "message": error_msg})
                return redirect("event_detail", event_id=event.id)

            print(f"🔍 DEBUG: Starting to process {total_rows} CSV rows...")

            # Create import log entry for progress tracking
            from .models import CSVImportLog

            import_log = CSVImportLog.objects.create(
                event=event,
                user=request.user,
                total_rows=total_rows,
                status="in_progress",
            )

            # Start background import process
            import threading
            from django.utils import timezone

            def background_import():
                """Background CSV import with progress tracking"""
                try:
                    print(
                        f"🔄 Starting background CSV import for event: {event.event_name}"
                    )
                    print(f"📋 Total rows to process: {total_rows}")

                    imported_count = 0
                    error_count = 0
                    errors = []
                    processed_emails = set()

                    for row_num, row in enumerate(
                        data_rows, start=2
                    ):  # Start at 2 because header is row 1
                        # Update progress
                        import_log.processed_rows = (
                            row_num - 1
                        )  # Actual row number processed
                        import_log.save(update_fields=["processed_rows"])

                        print(f"📋 Processing row {row_num}/{total_rows + 1}: {row}")

                        if not any(row):  # Skip empty rows
                            print(f"⏭️ Skipping empty row {row_num}")
                            continue

                        if len(row) != len(clean_headers):
                            error_msg = f"Row {row_num}: Column count mismatch (expected {len(clean_headers)}, got {len(row)})"
                            errors.append(error_msg)
                            import_log.error_messages.append(error_msg)
                            import_log.failed_imports += 1
                            error_count += 1
                            continue

                        # Create data dictionary
                        row_data = dict(zip(clean_headers, row))

                        # Validate required fields
                        if not row_data.get("name", "").strip():
                            error_msg = f"Row {row_num}: Name is required"
                            errors.append(error_msg)
                            import_log.error_messages.append(error_msg)
                            import_log.failed_imports += 1
                            error_count += 1
                            continue

                        email = row_data.get("email", "").strip()
                        if not email:
                            error_msg = f"Row {row_num}: Email is required"
                            errors.append(error_msg)
                            import_log.error_messages.append(error_msg)
                            import_log.failed_imports += 1
                            error_count += 1
                            continue

                        # Check for duplicate email within this CSV
                        if email in processed_emails:
                            error_msg = (
                                f"Row {row_num}: Duplicate email {email} found in CSV"
                            )
                            errors.append(error_msg)
                            import_log.error_messages.append(error_msg)
                            import_log.failed_imports += 1
                            error_count += 1
                            continue

                        # Check for duplicate email in this event
                        if Participant.objects.filter(
                            event=event, email=email
                        ).exists():
                            error_msg = f"Row {row_num}: Email {email} already exists for this event"
                            errors.append(error_msg)
                            import_log.error_messages.append(error_msg)
                            import_log.failed_imports += 1
                            error_count += 1
                            continue

                        try:
                            # Create participant - CSV imports always start as pending
                            approval_status = "pending"
                            print(
                                f"📋 CSV Import - setting {row_data['name']} to pending status (requires manual approval)"
                            )

                            # Process custom fields
                            submitted_data = {}
                            for field in custom_fields:
                                if (
                                    field.label in row_data
                                    and row_data[field.label].strip()
                                ):
                                    value = row_data[field.label].strip()
                                    if field.field_type == "checkbox":
                                        submitted_data[field.label] = value.lower() in [
                                            "true",
                                            "1",
                                            "yes",
                                        ]
                                    elif field.field_type == "number":
                                        try:
                                            submitted_data[field.label] = float(value)
                                        except ValueError:
                                            error_msg = f"Row {row_num}: Invalid number for {field.label}: {value}"
                                            errors.append(error_msg)
                                            import_log.error_messages.append(error_msg)
                                            import_log.failed_imports += 1
                                            error_count += 1
                                            continue
                                    elif field.field_type == "multiselect":
                                        submitted_data[field.label] = [
                                            v.strip() for v in value.split(",")
                                        ]
                                    else:
                                        submitted_data[field.label] = value

                            # Create participant
                            participant = Participant.objects.create(
                                event=event,
                                name=row_data["name"].strip(),
                                email=email,
                                phone=row_data.get("phone", "").strip(),
                                approval_status=approval_status,
                                submitted_data=(
                                    submitted_data if submitted_data else None
                                ),
                            )

                            processed_emails.add(email)
                            import_log.successful_imports += 1
                            imported_count += 1
                            print(
                                f"✅ Successfully created participant {imported_count}: {participant.name} (Status: pending - awaiting manual approval)"
                            )

                            # All CSV imports are pending - tickets will be generated upon manual approval
                            if event.tickets:
                                print(
                                    f"🎫 Tickets will be generated upon manual approval: {participant.name}"
                                )
                            else:
                                print(
                                    f"ℹ️ No tickets for this event: {participant.name}"
                                )

                        except Exception as e:
                            error_msg = (
                                f"Row {row_num}: Error creating participant: {str(e)}"
                            )
                            errors.append(error_msg)
                            import_log.error_messages.append(error_msg)
                            import_log.failed_imports += 1
                            error_count += 1
                            print(f"❌ {error_msg}")
                            continue

                    # Mark as completed
                    import_log.status = "completed"
                    import_log.completed_at = timezone.now()
                    import_log.save()

                    print(
                        f"🏁 Background import completed: {imported_count} imported, {error_count} errors"
                    )

                except Exception as e:
                    import_log.status = "failed"
                    import_log.completed_at = timezone.now()
                    import_log.error_messages.append(f"Import failed: {str(e)}")
                    import_log.save()
                    print(f"❌ Background import failed: {e}")

            # Start the background thread
            thread = threading.Thread(target=background_import)
            thread.daemon = True
            thread.start()

            # Return JSON response for AJAX handling
            return JsonResponse(
                {
                    "status": "started",
                    "import_id": import_log.id,
                    "total_rows": total_rows,
                    "message": f"Import started for {total_rows} rows",
                    "redirect_url": f"/events/{event.id}/",
                }
            )

        except Exception as e:
            error_msg = f"Error processing CSV file: {str(e)}"
            messages.error(request, error_msg)
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"status": "error", "message": error_msg})
            return redirect("event_detail", event_id=event.id)

    return redirect("event_detail", event_id=event.id)


@login_required
def check_import_progress(request, import_id):
    """Check the progress of CSV import"""
    from .models import CSVImportLog
    from django.http import JsonResponse

    try:
        import_log = get_object_or_404(CSVImportLog, id=import_id, user=request.user)

        response_data = {
            "status": import_log.status,
            "progress_percentage": import_log.progress_percentage,
            "processed_rows": import_log.processed_rows,
            "total_rows": import_log.total_rows,
            "successful_imports": import_log.successful_imports,
            "failed_imports": import_log.failed_imports,
            "error_messages": (
                import_log.error_messages[-5:] if import_log.error_messages else []
            ),  # Last 5 errors
        }

        # Add completion data if finished
        if import_log.status in ["completed", "failed"]:
            response_data["completed_at"] = (
                import_log.completed_at.isoformat() if import_log.completed_at else None
            )
            response_data["redirect_url"] = f"/events/{import_log.event.id}/"

        return JsonResponse(response_data)

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@login_required
def generate_participant_certificate(request, event_id, participant_id):
    from .utils import generate_certificate_for_participant

    event = get_object_or_404(Event, id=event_id)
    participant = get_object_or_404(Participant, id=participant_id, event=event)

    # Use the shared utility function that contains the proven working logic
    success, message = generate_certificate_for_participant(event, participant)

    if success:
        messages.success(request, message)
    else:
        messages.error(request, message)

    return redirect("event_detail", event_id=event.id)


def bulk_generate_certificates(request, event_id):
    """Generate certificates for all participants - with detailed debugging"""
    from django.http import JsonResponse
    from django.contrib import messages
    import tempfile
    import os
    import pypdf
    from django.core.files.base import ContentFile
    import logging
    import traceback

    # Set up logging
    logger = logging.getLogger(__name__)

    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "POST method required"})

    event = get_object_or_404(Event, id=event_id)
    print(f"🔍 DEBUG: Event loaded: {event.event_name}")
    print(
        f"🔍 DEBUG: Certificate file: {event.certificate.name if event.certificate else 'None'}"
    )

    # Check if certificate template exists
    if not event.certificate:
        return JsonResponse(
            {
                "status": "error",
                "message": "No certificate template found for this event.",
            }
        )

    # Get all participants
    participants = Participant.objects.filter(event=event)
    print(f"🔍 DEBUG: Found {participants.count()} participants")

    if not participants.exists():
        return JsonResponse(
            {"status": "error", "message": "No participants found for this event."}
        )

    # Run bulk generation synchronously (no threading)
    successful = 0
    failed = 0

    print(
        f"Starting bulk certificate generation for {participants.count()} participants..."
    )

    # Simple for loop - use the shared utility function with proven working logic
    for participant in participants:
        try:
            print(f"Generating certificate for: {participant.name}")

            # Use the EXACT same utility function as individual generation
            from .utils import generate_certificate_for_participant

            success, message = generate_certificate_for_participant(event, participant)

            if success:
                successful += 1
                print(f"✅ {message}")
            else:
                failed += 1
                print(f"❌ {message}")

        except Exception as e:
            failed += 1
            print(f"❌ Exception generating certificate for {participant.name}: {e}")

    print(
        f"Bulk certificate generation completed: {successful} successful, {failed} failed"
    )

    # Return results immediately
    return JsonResponse(
        {
            "status": "completed",
            "message": f"Bulk certificate generation completed: {successful} successful, {failed} failed",
            "successful": successful,
            "failed": failed,
            "total": participants.count(),
        }
    )
