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
from django.db.models import Q, Case, When, Value, IntegerField, F, Window, Count
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

from .utils import (
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
from core.tasks import (
    test_hello,
    send_ticket_email_task,
    send_bulk_rsvp_emails_task,
    bulk_generate_certificates_task,
    bulk_send_certificates_task,
)
import threading

from .models import Event, Participant, Attendance
from .forms import EventForm, ParticipantForm
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.timezone import now


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
            ),
            valid_participant_count=Count(
                "participant", filter=~Q(participant__approval_status="rejected")
            ),
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

    valid_participant_count = participants.exclude(approval_status="rejected").count()
    from_dashboard = request.GET.get("from_dashboard") == "1"
    context = {
        "event": event,
        "participants": participants,
        "present_participants": participants.filter(id__in=present_participants),
        "not_present_participants": not_present_participants,
        "missing_email_templates": missing_email_templates,
        "missing_email_templates_json": missing_email_templates_json,
        "rsvp_template_missing": rsvp_template_missing,
        "valid_participant_count": valid_participant_count,
        "from_dashboard": from_dashboard,
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

    # Get all APPROVED participants for the event
    all_participants = Participant.objects.filter(
        event=event, approval_status="approved"
    )

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

        # Check if participant is approved
        if participant.approval_status != "approved":
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Invalid ticket. Participant is not approved for this event.",
                    "participant_name": participant.name,
                    "participant_approval_status": participant.approval_status,
                },
                status=400,
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
                    "participant_name": participant.name,
                    "participant_approval_status": participant.approval_status,
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

        # Get counts for approved participants only
        total_present = Attendance.objects.filter(
            event=event, present=True, participant__approval_status="approved"
        ).count()
        total_registered = Participant.objects.filter(
            event=event, approval_status="approved"
        ).count()
        not_present = total_registered - total_present

        return JsonResponse(
            {
                "status": "success",
                "message": f"{participant.name} checked in successfully.",
                "participant_name": participant.name,
                "participant_approval_status": participant.approval_status,
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
    """Handles sending ticket email manually via AJAX request using Celery task"""

    print("send_ticket_email_view")

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

        # ✅ Send email using Celery task (non-blocking)
        task = send_ticket_email_task.delay(participant_id)
        print(
            f"✅ Celery task {task.id} queued for sending ticket email to {participant.email}"
        )

        return JsonResponse(
            {"status": "success", "message": "Ticket email queued for sending!"},
            status=200,
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
    if not event.status or event.status.name.lower() != "ongoing":
        return render(request, "registration_closed.html", {"event": event})

    # Check registration limit if enabled
    if event.has_registration_limit and event.registration_limit:
        current_participants = (
            Participant.objects.filter(event=event)
            .exclude(approval_status="rejected")
            .count()
        )
        if current_participants >= event.registration_limit:
            return render(
                request,
                "registration_closed.html",
                {"event": event, "reason": "limit_reached"},
            )

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
        ("certificates", "Certificate Generation Email"),
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
    valid_reasons = ["registration", "approval", "rejection", "rsvp", "certificates"]
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

        # Enforce RSVP cutoff
        if hasattr(event, "rsvp_is_open") and not event.rsvp_is_open:
            messages.error(request, "RSVP for this event is closed and no longer accepts responses.")
            return render(request, "rsvp_error.html", {"event": event, "error": "RSVP for this event is closed."})

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

            # Enforce RSVP cutoff
            if hasattr(event, "rsvp_is_open") and not event.rsvp_is_open:
                return JsonResponse({"error": "RSVP for this event is closed."}, status=403)

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

        # Enforce RSVP cutoff for GET (form display)
        if hasattr(event, "rsvp_is_open") and not event.rsvp_is_open:
            return render(request, "rsvp_error.html", {"event": event, "error": "RSVP for this event is closed."})

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
    from .models import RSVPEmailLog
    from django.utils import timezone

    event = get_object_or_404(Event, id=event_id)
    participant = get_object_or_404(Participant, id=participant_id, event=event)

    # Check if an RSVP email template exists
    if not EventEmail.objects.filter(event=event, reason="rsvp").exists():
        messages.error(
            request,
            f"No RSVP email template found for this event. Please create one first.",
        )
        return redirect("event_detail", event_id=event.id)

    # Create RSVP email log entry for individual sending
    email_log = RSVPEmailLog.objects.create(
        event=event,
        user=request.user,
        total_recipients=1,
        emails_sent=0,
        emails_failed=0,
        status="in_progress",
        log_messages=[],
    )

    try:
        # Call the email sending function from signals.py
        send_rsvp_email(participant)

        # Update log for success
        email_log.emails_sent = 1
        email_log.status = "completed"
        email_log.log_messages.append(
            {
                "type": "success",
                "timestamp": timezone.now().isoformat(),
                "message": f"Successfully sent RSVP email to {participant.name} ({participant.email})",
                "participant": f"{participant.name} ({participant.email})",
                "email_type": "rsvp",
                "operation_type": "individual_sending",
            }
        )
        email_log.completed_at = timezone.now()
        email_log.save()

        messages.success(
            request, f"RSVP email sent successfully to {participant.name}."
        )
    except Exception as e:
        # Update log for failure
        email_log.emails_failed = 1
        email_log.status = "failed"
        email_log.log_messages.append(
            {
                "type": "error",
                "timestamp": timezone.now().isoformat(),
                "message": f"Failed to send RSVP email to {participant.name} ({participant.email}): {str(e)}",
                "participant": f"{participant.name} ({participant.email})",
                "email_type": "rsvp",
                "operation_type": "individual_sending",
                "error_details": str(e),
            }
        )
        email_log.completed_at = timezone.now()
        email_log.save()

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

    # Start background email sending using Celery task
    participant_ids = list(eligible_participants.values_list("id", flat=True))
    task = send_bulk_rsvp_emails_task.delay(event_id, participant_ids, request.user.id)
    print(
        f"✅ Celery task {task.id} queued for sending bulk RSVP emails to {len(participant_ids)} participants"
    )

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
                "log_messages": (
                    email_log.log_messages[-5:] if email_log.log_messages else []
                ),  # Last 5 log entries
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
                            import_log.log_messages.append(
                                {
                                    "type": "error",
                                    "timestamp": timezone.now().isoformat(),
                                    "message": error_msg,
                                    "row": row_num,
                                }
                            )
                            import_log.failed_imports += 1
                            error_count += 1
                            import_log.save()
                            continue

                        # Create data dictionary
                        row_data = dict(zip(clean_headers, row))

                        # Validate required fields
                        if not row_data.get("name", "").strip():
                            error_msg = f"Row {row_num}: Name is required"
                            errors.append(error_msg)
                            import_log.log_messages.append(
                                {
                                    "type": "error",
                                    "timestamp": timezone.now().isoformat(),
                                    "message": error_msg,
                                    "row": row_num,
                                }
                            )
                            import_log.failed_imports += 1
                            error_count += 1
                            import_log.save()
                            continue

                        email = row_data.get("email", "").strip()
                        if not email:
                            error_msg = f"Row {row_num}: Email is required"
                            errors.append(error_msg)
                            import_log.log_messages.append(
                                {
                                    "type": "error",
                                    "timestamp": timezone.now().isoformat(),
                                    "message": error_msg,
                                    "row": row_num,
                                }
                            )
                            import_log.failed_imports += 1
                            error_count += 1
                            import_log.save()
                            continue

                        # Check for duplicate email within this CSV
                        if email in processed_emails:
                            error_msg = (
                                f"Row {row_num}: Duplicate email {email} found in CSV"
                            )
                            errors.append(error_msg)
                            import_log.log_messages.append(
                                {
                                    "type": "error",
                                    "timestamp": timezone.now().isoformat(),
                                    "message": error_msg,
                                    "row": row_num,
                                }
                            )
                            import_log.failed_imports += 1
                            error_count += 1
                            import_log.save()
                            continue

                        # Check for duplicate email in this event
                        if Participant.objects.filter(
                            event=event, email=email
                        ).exists():
                            error_msg = f"Row {row_num}: Email {email} already exists for this event"
                            errors.append(error_msg)
                            import_log.log_messages.append(
                                {
                                    "type": "error",
                                    "timestamp": timezone.now().isoformat(),
                                    "message": error_msg,
                                    "row": row_num,
                                }
                            )
                            import_log.failed_imports += 1
                            error_count += 1
                            import_log.save()
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
                                            import_log.log_messages.append(
                                                {
                                                    "type": "error",
                                                    "timestamp": timezone.now().isoformat(),
                                                    "message": error_msg,
                                                    "row": row_num,
                                                }
                                            )
                                            import_log.failed_imports += 1
                                            error_count += 1
                                            import_log.save()
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

                            # Log success
                            import_log.log_messages.append(
                                {
                                    "type": "success",
                                    "timestamp": timezone.now().isoformat(),
                                    "message": f"Successfully imported participant: {participant.name} ({participant.email})",
                                    "row": row_num,
                                }
                            )
                            import_log.save()

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
                            import_log.log_messages.append(
                                {
                                    "type": "error",
                                    "timestamp": timezone.now().isoformat(),
                                    "message": error_msg,
                                    "row": row_num,
                                }
                            )
                            import_log.failed_imports += 1
                            error_count += 1
                            import_log.save()
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
                    import_log.log_messages.append(
                        {
                            "type": "error",
                            "timestamp": timezone.now().isoformat(),
                            "message": f"Import failed: {str(e)}",
                            "row": None,
                        }
                    )
                    import_log.save()
                    print(f"❌ Background import failed: {e}")

            # Start the background import using threading
            import_thread = threading.Thread(target=background_import)
            import_thread.daemon = True
            import_thread.start()
            print(f"✅ Thread started for CSV import with {total_rows} rows")

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
            "log_messages": (
                import_log.log_messages[-5:] if import_log.log_messages else []
            ),  # Last 5 log entries
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
    from .models import CertificateGenerationLog
    from django.utils import timezone

    event = get_object_or_404(Event, id=event_id)
    participant = get_object_or_404(Participant, id=participant_id, event=event)

    # Check if certificate template exists
    if not event.certificate:
        messages.error(request, "No certificate template found for this event.")
        return redirect("event_detail", event_id=event.id)

    # Create certificate generation log entry for individual generation
    cert_log = CertificateGenerationLog.objects.create(
        event=event,
        user=request.user,
        total_participants=1,
        processed_participants=0,
        successful_generations=0,
        failed_generations=0,
        status="in_progress",
        log_messages=[],
    )

    try:
        # Use the shared utility function that contains the proven working logic
        success, message = generate_certificate_for_participant(event, participant)

        # Update log based on result
        cert_log.processed_participants = 1
        if success:
            cert_log.successful_generations = 1
            cert_log.status = "completed"
            cert_log.log_messages.append(
                {
                    "type": "success",
                    "timestamp": timezone.now().isoformat(),
                    "message": f"Successfully generated certificate for {participant.name} ({participant.email})",
                    "participant": f"{participant.name} ({participant.email})",
                    "operation_type": "individual_generation",
                }
            )
            messages.success(request, message)
        else:
            cert_log.failed_generations = 1
            cert_log.status = "failed"
            cert_log.log_messages.append(
                {
                    "type": "error",
                    "timestamp": timezone.now().isoformat(),
                    "message": f"Failed to generate certificate for {participant.name} ({participant.email}): {message}",
                    "participant": f"{participant.name} ({participant.email})",
                    "operation_type": "individual_generation",
                    "error_details": message,
                }
            )
            messages.error(request, message)

        cert_log.completed_at = timezone.now()
        cert_log.save()

    except Exception as e:
        # Handle any unexpected errors
        cert_log.processed_participants = 1
        cert_log.failed_generations = 1
        cert_log.status = "failed"
        cert_log.log_messages.append(
            {
                "type": "error",
                "timestamp": timezone.now().isoformat(),
                "message": f"Exception occurred while generating certificate for {participant.name} ({participant.email}): {str(e)}",
                "participant": f"{participant.name} ({participant.email})",
                "operation_type": "individual_generation",
                "error_details": str(e),
            }
        )
        cert_log.completed_at = timezone.now()
        cert_log.save()

        messages.error(request, f"Error generating certificate: {str(e)}")

    return redirect("event_detail", event_id=event.id)


@login_required
def bulk_generate_certificates(request, event_id):
    """Generate certificates for all participants using Celery background task"""
    from django.http import JsonResponse
    from .models import CertificateGenerationLog, Attendance

    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "POST method required"})

    event = get_object_or_404(Event, id=event_id)

    # Check if certificate template exists
    if not event.certificate:
        return JsonResponse(
            {
                "status": "error",
                "message": "No certificate template found for this event.",
            }
        )

    # Get participants who have attended the event
    attended_participants = Participant.objects.filter(
        event=event, attendance__event=event, attendance__present=True
    ).distinct()

    if not attended_participants.exists():
        return JsonResponse(
            {
                "status": "error",
                "message": "No participants with attendance records found for this event.",
            }
        )

    # Create certificate generation log entry
    cert_log = CertificateGenerationLog.objects.create(
        event=event,
        user=request.user,
        total_participants=attended_participants.count(),
        status="in_progress",
    )

    # Start background certificate generation using Celery task
    task = bulk_generate_certificates_task.delay(event.id, request.user.id)
    print(
        f"✅ Celery task {task.id} queued for bulk certificate generation for {attended_participants.count()} participants"
    )

    return JsonResponse(
        {
            "status": "started",
            "log_id": cert_log.id,
            "total_participants": attended_participants.count(),
            "message": f"Certificate generation started for {attended_participants.count()} participants",
        }
    )


@login_required
def check_certificate_generation_progress(request, log_id):
    """Check the progress of certificate generation"""
    from .models import CertificateGenerationLog
    from django.http import JsonResponse

    try:
        cert_log = get_object_or_404(
            CertificateGenerationLog, id=log_id, user=request.user
        )

        response_data = {
            "status": cert_log.status,
            "progress_percentage": cert_log.progress_percentage,
            "processed_participants": cert_log.processed_participants,
            "total_participants": cert_log.total_participants,
            "successful_generations": cert_log.successful_generations,
            "failed_generations": cert_log.failed_generations,
            "log_messages": (
                cert_log.log_messages[-5:] if cert_log.log_messages else []
            ),  # Last 5 log entries
        }

        # Add completion data if finished
        if cert_log.status in ["completed", "failed"]:
            response_data["completed_at"] = (
                cert_log.completed_at.isoformat() if cert_log.completed_at else None
            )
            response_data["redirect_url"] = f"/events/{cert_log.event.id}/"

        return JsonResponse(response_data)

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@login_required
def bulk_send_certificates(request, event_id):
    """Send certificates to all participants who have certificates generated using Celery background task"""
    from django.http import JsonResponse
    from .models import CertificateGenerationLog

    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "POST method required"})

    event = get_object_or_404(Event, id=event_id)

    # Check if certificate template exists
    if not event.certificate:
        return JsonResponse(
            {
                "status": "error",
                "message": "No certificate template found for this event.",
            }
        )

    # Check if email template for certificates exists
    if not EventEmail.objects.filter(event=event, reason="certificates").exists():
        return JsonResponse(
            {
                "status": "error",
                "message": "No email template found for sending certificates. Please create one first.",
            }
        )

    # Start the Celery task
    bulk_send_certificates_task.delay(event_id, request.user.id)

    return JsonResponse(
        {
            "status": "started",
            "message": "Certificate sending process has been started. You will be notified when it's complete.",
        }
    )


@login_required
def edit_participant_view(request, event_id, participant_id):
    event = get_object_or_404(Event, id=event_id)
    participant = get_object_or_404(Participant, id=participant_id, event=event)

    if request.method == "POST":
        form = ParticipantForm(
            request.POST, request.FILES, event=event, instance=participant
        )
        if form.is_valid():
            try:
                participant = form.save(commit=False)

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

                            # Delete old file if it exists
                            ParticipantCustomFieldFile.objects.filter(
                                participant=participant, field_label=field_model.label
                            ).delete()

                            # Create new file entry
                            ParticipantCustomFieldFile.objects.create(
                                participant=participant,
                                field_label=field_model.label,
                                file=value,
                            )

                messages.success(
                    request, f"✅ Participant {participant.name} updated successfully."
                )
                return redirect("event_detail", event_id=event.id)

            except IntegrityError:
                # Handle duplicate email error
                email = form.cleaned_data.get("email", "")
                messages.error(
                    request,
                    f"❌ This email address ({email}) is already registered for this event. Please use a different email address.",
                )
    else:
        # Initialize form with participant's data
        initial_data = {}

        # Add custom field data
        if participant.submitted_data:
            custom_fields = EventCustomField.objects.filter(event=event)
            for field in custom_fields:
                field_name = f"custom_field_{field.id}"
                if field.label in participant.submitted_data:
                    initial_data[field_name] = participant.submitted_data[field.label]

        form = ParticipantForm(instance=participant, event=event, initial=initial_data)

    return render(
        request,
        "edit_participant.html",
        {"form": form, "event": event, "participant": participant},
    )


@login_required
def dashboard(request):
    """Dashboard view: Event timeline/calendar and participant insights."""
    from .models import Event, Participant, Status

    # Get all statuses for filter UI
    all_statuses = list(Status.objects.all())
    filter_status = request.GET.get("timeline_status", "active")  # 'active' or 'all'
    filter_year = request.GET.get("year", "")  # Year filter

    # Base queryset
    base_events = Event.objects.select_related("status").annotate(
        participant_count=Count("participant")
    )

    # Apply status filter
    if filter_status == "active":
        filtered_statuses = ["Planned", "Ongoing"]
        base_events = base_events.filter(status__name__in=filtered_statuses)

    # Apply year filter
    if filter_year:
        base_events = base_events.filter(event_date__year=filter_year)

    # Get filtered events
    events = base_events.order_by("event_date", "start_time")

    # Get available years for filter dropdown
    available_years = Event.objects.dates("event_date", "year", order="DESC")

    # Filter participants for insights based on filtered events
    filtered_event_ids = list(events.values_list("id", flat=True))
    participants_queryset = Participant.objects.filter(event_id__in=filtered_event_ids)

    # Prepare calendar events with color
    calendar_events = []
    for event in events:
        color = event.status.color if event.status and event.status.color else "#2563eb"
        calendar_events.append(
            {
                "title": event.event_name,
                "start": str(event.event_date),
                "color": color,
                "url": f"/events/{event.id}/?from_dashboard=1",
            }
        )

    # Participant insights based on filtered events
    total_participants = participants_queryset.count()
    approved_participants = participants_queryset.filter(
        approval_status="approved"
    ).count()
    pending_participants = participants_queryset.filter(
        approval_status="pending"
    ).count()
    rejected_participants = participants_queryset.filter(
        approval_status="rejected"
    ).count()
    participants_per_event = participants_queryset.values("event__event_name").annotate(
        count=Count("id"),
        pending_count=Count("id", filter=Q(approval_status="pending")),
    )

    # Add capacity information for each event
    for item in participants_per_event:
        event = Event.objects.get(event_name=item["event__event_name"])
        approved_count = Participant.objects.filter(
            event=event, approval_status="approved"
        ).count()

        item["has_limit"] = event.has_registration_limit
        item["capacity_limit"] = (
            event.registration_limit if event.has_registration_limit else None
        )
        item["approved_count"] = approved_count
        item["available_spots"] = (
            event.registration_limit - approved_count - item["pending_count"]
            if event.has_registration_limit and event.registration_limit
            else None
        )
        item["is_full"] = (
            event.has_registration_limit
            and event.registration_limit
            and (approved_count + item["pending_count"]) >= event.registration_limit
        )

    context = {
        "events": events,
        "calendar_events": calendar_events,
        "total_participants": total_participants,
        "approved_participants": approved_participants,
        "pending_participants": pending_participants,
        "rejected_participants": rejected_participants,
        "participants_per_event": participants_per_event,
        "all_statuses": all_statuses,
        "timeline_status": filter_status,
        "available_years": available_years,
        "selected_year": filter_year,
    }
    return render(request, "dashboard.html", context)


@login_required
def dashboard_pending_participants(request):
    """AJAX endpoint to get pending participants for a specific event."""
    from django.http import JsonResponse

    event_name = request.GET.get("event_name")
    if not event_name:
        return JsonResponse({"error": "Event name is required"}, status=400)

    try:
        event = Event.objects.get(event_name=event_name)
        pending_participants = Participant.objects.filter(
            event=event, approval_status="pending"
        ).values("id", "name", "email", "registered_at")

        # Get capacity statistics
        total_participants = Participant.objects.filter(event=event).count()
        approved_participants = Participant.objects.filter(
            event=event, approval_status="approved"
        ).count()
        rejected_participants = Participant.objects.filter(
            event=event, approval_status="rejected"
        ).count()
        pending_count = pending_participants.count()

        # Calculate capacity info
        has_limit = event.has_registration_limit
        capacity_limit = event.registration_limit if has_limit else None
        available_spots = (
            capacity_limit - approved_participants - pending_count
            if has_limit and capacity_limit
            else None
        )

        # Format the data
        participants_data = []
        for participant in pending_participants:
            participants_data.append(
                {
                    "id": participant["id"],
                    "name": participant["name"],
                    "email": participant["email"],
                    "registered_at": participant["registered_at"].strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                }
            )

        return JsonResponse(
            {
                "participants": participants_data,
                "event_name": event_name,
                "capacity_stats": {
                    "total_participants": total_participants,
                    "approved_participants": approved_participants,
                    "rejected_participants": rejected_participants,
                    "pending_count": pending_count,
                    "has_limit": has_limit,
                    "capacity_limit": capacity_limit,
                    "available_spots": available_spots,
                },
            }
        )

    except Event.DoesNotExist:
        return JsonResponse({"error": "Event not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def reports(request):
    """Reports page with various report cards."""
    from .models import Event, Participant, Status, RSVPResponse

    report_type = request.GET.get("report_type")
    selected_event_ids = (
        request.GET.get("event_ids", "").split(",")
        if request.GET.get("event_ids")
        else []
    )
    selected_event_ids = [eid.strip() for eid in selected_event_ids if eid.strip()]

    if report_type == "registration_summary":
        # Get all events for the dropdown
        all_events = Event.objects.select_related("status").order_by("event_date")

        # Filter events based on selection
        if selected_event_ids:
            events = all_events.filter(id__in=selected_event_ids)
        else:
            events = all_events

        # Get all events with participant counts
        events = (
            events.select_related("status")
            .annotate(
                total_participants=Count("participant"),
                approved_participants=Count(
                    "participant", filter=Q(participant__approval_status="approved")
                ),
                pending_participants=Count(
                    "participant", filter=Q(participant__approval_status="pending")
                ),
                rejected_participants=Count(
                    "participant", filter=Q(participant__approval_status="rejected")
                ),
            )
            .order_by("event_date")
        )

        # Add RSVP statistics for each event
        for event in events:
            rsvp_responses = RSVPResponse.objects.filter(event=event)
            event.rsvp_attend = rsvp_responses.filter(response="attend").count()
            event.rsvp_cant_make_it = rsvp_responses.filter(
                response="cant_make_it"
            ).count()
            event.rsvp_maybe = rsvp_responses.filter(response="maybe").count()
            event.total_rsvp_responses = rsvp_responses.count()

            # Calculate RSVP response rate
            if event.total_participants > 0:
                event.rsvp_response_rate = round(
                    (event.total_rsvp_responses / event.total_participants) * 100, 1
                )
            else:
                event.rsvp_response_rate = 0

        # Calculate overall statistics
        total_events = events.count()
        total_participants = sum(event.total_participants for event in events)
        total_approved = sum(event.approved_participants for event in events)
        total_pending = sum(event.pending_participants for event in events)
        total_rejected = sum(event.rejected_participants for event in events)

        # Calculate overall RSVP statistics
        total_rsvp_attend = sum(event.rsvp_attend for event in events)
        total_rsvp_cant_make_it = sum(event.rsvp_cant_make_it for event in events)
        total_rsvp_maybe = sum(event.rsvp_maybe for event in events)
        total_rsvp_responses = sum(event.total_rsvp_responses for event in events)

        # Calculate overall RSVP response rate
        if total_participants > 0:
            overall_rsvp_response_rate = round(
                (total_rsvp_responses / total_participants) * 100, 1
            )
        else:
            overall_rsvp_response_rate = 0

        context = {
            "events": events,
            "all_events": all_events,
            "selected_event_ids": selected_event_ids,
            "total_events": total_events,
            "total_participants": total_participants,
            "total_approved": total_approved,
            "total_pending": total_pending,
            "total_rejected": total_rejected,
            "total_rsvp_attend": total_rsvp_attend,
            "total_rsvp_cant_make_it": total_rsvp_cant_make_it,
            "total_rsvp_maybe": total_rsvp_maybe,
            "total_rsvp_responses": total_rsvp_responses,
            "overall_rsvp_response_rate": overall_rsvp_response_rate,
            "report_type": report_type,
        }
        return render(request, "reports/registration_summary.html", context)

    elif report_type == "participant_summary":
        # Get all events for reference
        all_events = Event.objects.select_related("status").order_by("event_date")

        # Get all participants for filtering
        all_participants = Participant.objects.values_list(
            "email", flat=True
        ).distinct()

        # Get participant filter from request
        selected_participant_emails = (
            request.GET.get("participant_emails", "").split(",")
            if request.GET.get("participant_emails")
            else []
        )
        selected_participant_emails = [
            email.strip().lower()
            for email in selected_participant_emails
            if email.strip()
        ]

        # Get all events (no event filtering for participant summary)
        events = all_events

        # Get participants from all events, filter by selected emails if any
        if selected_participant_emails:
            participants = Participant.objects.filter(
                email__in=selected_participant_emails
            ).select_related("event")
        else:
            participants = Participant.objects.all().select_related("event")

        # Aggregate participants by email
        from collections import defaultdict

        participant_stats = defaultdict(
            lambda: {
                "email": "",
                "name": "",
                "total_registrations": 0,
                "approved_registrations": 0,
                "pending_registrations": 0,
                "rejected_registrations": 0,
                "events_registered": [],
                "rsvp_responses": 0,
                "rsvp_attend": 0,
                "rsvp_cant_make_it": 0,
                "rsvp_maybe": 0,
                "total_attendances": 0,
                "last_registration_date": None,
                "first_registration_date": None,
            }
        )

        for participant in participants:
            email = participant.email.lower()
            participant_stats[email]["email"] = participant.email
            participant_stats[email]["name"] = participant.name
            participant_stats[email]["total_registrations"] += 1

            # Count approval status
            if participant.approval_status == "approved":
                participant_stats[email]["approved_registrations"] += 1
            elif participant.approval_status == "pending":
                participant_stats[email]["pending_registrations"] += 1
            elif participant.approval_status == "rejected":
                participant_stats[email]["rejected_registrations"] += 1

            # Track events
            event_info = {
                "event_name": participant.event.event_name,
                "event_date": participant.event.event_date,
                "status": participant.approval_status,
                "registration_date": participant.registered_at,
            }
            participant_stats[email]["events_registered"].append(event_info)

            # Track registration dates
            if (
                not participant_stats[email]["first_registration_date"]
                or participant.registered_at
                < participant_stats[email]["first_registration_date"]
            ):
                participant_stats[email][
                    "first_registration_date"
                ] = participant.registered_at

            if (
                not participant_stats[email]["last_registration_date"]
                or participant.registered_at
                > participant_stats[email]["last_registration_date"]
            ):
                participant_stats[email][
                    "last_registration_date"
                ] = participant.registered_at

        # Add RSVP statistics
        for email, stats in participant_stats.items():
            rsvp_responses = RSVPResponse.objects.filter(participant__email=email)
            stats["rsvp_responses"] = rsvp_responses.count()
            stats["rsvp_attend"] = rsvp_responses.filter(response="attend").count()
            stats["rsvp_cant_make_it"] = rsvp_responses.filter(
                response="cant_make_it"
            ).count()
            stats["rsvp_maybe"] = rsvp_responses.filter(response="maybe").count()

        # Add attendance statistics
        for email, stats in participant_stats.items():
            attendances = Attendance.objects.filter(
                participant__email=email, present=True
            )
            stats["total_attendances"] = attendances.count()

        # Convert to list and sort by total registrations
        participant_list = list(participant_stats.values())
        participant_list.sort(key=lambda x: x["total_registrations"], reverse=True)

        # Calculate overall statistics
        total_unique_participants = len(participant_list)
        total_registrations = sum(p["total_registrations"] for p in participant_list)
        total_approved = sum(p["approved_registrations"] for p in participant_list)
        total_pending = sum(p["pending_registrations"] for p in participant_list)
        total_rejected = sum(p["rejected_registrations"] for p in participant_list)
        total_attendances = sum(p["total_attendances"] for p in participant_list)

        # Calculate average registrations per participant
        avg_registrations = (
            round(total_registrations / total_unique_participants, 1)
            if total_unique_participants > 0
            else 0
        )

        # Calculate attendance rate
        attendance_rate = (
            round((total_attendances / total_approved) * 100, 1)
            if total_approved > 0
            else 0
        )

        context = {
            "participants": participant_list,
            "all_participants": all_participants,
            "selected_participant_emails": selected_participant_emails,
            "total_unique_participants": total_unique_participants,
            "total_registrations": total_registrations,
            "total_approved": total_approved,
            "total_pending": total_pending,
            "total_rejected": total_rejected,
            "total_attendances": total_attendances,
            "avg_registrations": avg_registrations,
            "attendance_rate": attendance_rate,
            "report_type": report_type,
        }
        return render(request, "reports/participant_summary.html", context)

    # Main reports page with buttons
    context = {
        "report_type": None,
    }
    return render(request, "reports.html", context)


@login_required
def logs_view(request):
    """Display all system logs in a tabbed interface"""
    from .models import RSVPEmailLog, CertificateGenerationLog, CSVImportLog

    # Get logs for each type, ordered by most recent first
    rsvp_logs = RSVPEmailLog.objects.select_related("event", "user").order_by(
        "-started_at"
    )[:50]
    certificate_logs = CertificateGenerationLog.objects.select_related(
        "event", "user"
    ).order_by("-started_at")[:50]
    import_logs = CSVImportLog.objects.select_related("event", "user").order_by(
        "-started_at"
    )[:50]

    context = {
        "rsvp_logs": rsvp_logs,
        "certificate_logs": certificate_logs,
        "import_logs": import_logs,
    }

    return render(request, "logs.html", context)


@login_required
def log_details_ajax(request, log_type, log_id):
    """AJAX endpoint to get detailed log information"""
    from django.http import JsonResponse
    from .models import RSVPEmailLog, CertificateGenerationLog, CSVImportLog

    try:
        if log_type == "rsvp":
            log = RSVPEmailLog.objects.select_related("event", "user").get(id=log_id)
            stats_html = f"""
                <div><span class="font-medium">Total Recipients:</span> {log.total_recipients}</div>
                <div><span class="font-medium">Emails Sent:</span> {log.emails_sent}</div>
                <div><span class="font-medium">Emails Failed:</span> {log.emails_failed}</div>
                <div><span class="font-medium">Progress:</span> {log.progress_percentage}%</div>
            """
        elif log_type == "certificate":
            log = CertificateGenerationLog.objects.select_related("event", "user").get(
                id=log_id
            )
            stats_html = f"""
                <div><span class="font-medium">Total Participants:</span> {log.total_participants}</div>
                <div><span class="font-medium">Processed:</span> {log.processed_participants}</div>
                <div><span class="font-medium">Successful:</span> {log.successful_generations}</div>
                <div><span class="font-medium">Failed:</span> {log.failed_generations}</div>
            """
        elif log_type == "import":
            log = CSVImportLog.objects.select_related("event", "user").get(id=log_id)
            stats_html = f"""
                <div><span class="font-medium">Total Rows:</span> {log.total_rows}</div>
                <div><span class="font-medium">Processed Rows:</span> {log.processed_rows}</div>
                <div><span class="font-medium">Successful Imports:</span> {log.successful_imports}</div>
                <div><span class="font-medium">Failed Imports:</span> {log.failed_imports}</div>
            """
        else:
            return JsonResponse({"success": False, "error": "Invalid log type"})

        log_details = {
            "event_name": log.event.event_name,
            "user": log.user.username,
            "status": log.status,
            "started_at": log.started_at.strftime("%B %d, %Y at %H:%M:%S"),
            "completed_at": (
                log.completed_at.strftime("%B %d, %Y at %H:%M:%S")
                if log.completed_at
                else None
            ),
            "stats_html": stats_html,
            "log_messages": log.log_messages if hasattr(log, "log_messages") else [],
        }

        return JsonResponse({"success": True, "log_details": log_details})

    except (
        RSVPEmailLog.DoesNotExist,
        CertificateGenerationLog.DoesNotExist,
        CSVImportLog.DoesNotExist,
    ):
        return JsonResponse({"success": False, "error": "Log not found"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
def participant_detail(request, participant_email):
    """Individual participant statistics page."""
    from .models import Event, Participant, RSVPResponse, Attendance
    from collections import defaultdict

    # Get all participants with this email
    participants = (
        Participant.objects.filter(email__iexact=participant_email)
        .select_related("event")
        .order_by("event__event_date")
    )

    if not participants.exists():
        messages.error(
            request, f"No participants found with email: {participant_email}"
        )
        return redirect("reports")

    # Get the first participant for basic info (name, email)
    first_participant = participants.first()
    participant_name = first_participant.name
    participant_email_clean = first_participant.email

    # Calculate statistics
    total_registrations = participants.count()
    approved_registrations = participants.filter(approval_status="approved").count()
    pending_registrations = participants.filter(approval_status="pending").count()
    rejected_registrations = participants.filter(approval_status="rejected").count()

    # Get RSVP statistics
    rsvp_responses = RSVPResponse.objects.filter(
        participant__email__iexact=participant_email
    )
    total_rsvp_responses = rsvp_responses.count()
    rsvp_attend = rsvp_responses.filter(response="attend").count()
    rsvp_cant_make_it = rsvp_responses.filter(response="cant_make_it").count()
    rsvp_maybe = rsvp_responses.filter(response="maybe").count()

    # Get attendance statistics
    attendances = Attendance.objects.filter(
        participant__email__iexact=participant_email
    )
    total_attendances = attendances.filter(present=True).count()
    total_events_attended = (
        attendances.filter(present=True).values("event").distinct().count()
    )

    # Calculate attendance rate
    attendance_rate = 0
    if total_registrations > 0:
        attendance_rate = round((total_attendances / total_registrations) * 100, 1)

    # Get registration dates
    first_registration = participants.order_by("registered_at").first()
    last_registration = participants.order_by("registered_at").last()

    # Get events registered for with details
    events_registered = []
    for participant in participants:
        # Get RSVP for this event
        rsvp = RSVPResponse.objects.filter(
            participant=participant, event=participant.event
        ).first()

        # Get attendance for this event
        attendance = Attendance.objects.filter(
            participant=participant, event=participant.event
        ).first()

        event_info = {
            "event": participant.event,
            "registration_date": participant.registered_at,
            "approval_status": participant.approval_status,
            "rsvp_response": rsvp.response if rsvp else None,
            "rsvp_notes": rsvp.notes if rsvp else None,
            "attended": attendance.present if attendance else False,
            "has_ticket": bool(participant.pdf_ticket),
            "has_certificate": bool(participant.certificate),
        }
        events_registered.append(event_info)

    # Sort events by date
    events_registered.sort(key=lambda x: x["event"].event_date, reverse=True)

    # Get most recent activity
    most_recent_activity = None
    if events_registered:
        most_recent_activity = max(
            events_registered, key=lambda x: x["registration_date"]
        )

    context = {
        "participant_name": participant_name,
        "participant_email": participant_email_clean,
        "total_registrations": total_registrations,
        "approved_registrations": approved_registrations,
        "pending_registrations": pending_registrations,
        "rejected_registrations": rejected_registrations,
        "total_rsvp_responses": total_rsvp_responses,
        "rsvp_attend": rsvp_attend,
        "rsvp_cant_make_it": rsvp_cant_make_it,
        "rsvp_maybe": rsvp_maybe,
        "total_attendances": total_attendances,
        "total_events_attended": total_events_attended,
        "attendance_rate": attendance_rate,
        "first_registration_date": (
            first_registration.registered_at if first_registration else None
        ),
        "last_registration_date": (
            last_registration.registered_at if last_registration else None
        ),
        "events_registered": events_registered,
        "most_recent_activity": most_recent_activity,
    }

    return render(request, "reports/participant_detail.html", context)



@login_required
def event_attendance_dashboard(request, event_id):
    """
    Real-time attendance dashboard showing present and not present participants
    """
    event = get_object_or_404(Event, id=event_id)

    # Get all participants for this event
    participants = Participant.objects.filter(
        event=event, approval_status="approved"
    ).order_by("name")

    # Get attendance records
    attendance_records = Attendance.objects.filter(event=event).select_related(
        "participant"
    )

    # Create dictionaries for quick lookup
    attendance_dict = {att.participant.id: att for att in attendance_records}

    # Categorize participants
    present_participants = []
    not_present_participants = []

    for participant in participants:
        attendance = attendance_dict.get(participant.id)
        participant_data = {
            "id": participant.id,
            "name": participant.name,
            "email": participant.email,
            "phone": participant.phone,
            "registered_at": participant.registered_at,
            "attendance_timestamp": (
                attendance.timestamp if attendance and attendance.present else None
            ),
            "has_signature": (
                bool(attendance and attendance.signature_file) if attendance else False
            ),
        }

        if attendance and attendance.present:
            present_participants.append(participant_data)
        else:
            not_present_participants.append(participant_data)

    # Sort by attendance timestamp for present participants, and by name for not present
    present_participants.sort(key=lambda x: x["attendance_timestamp"], reverse=True)
    not_present_participants.sort(key=lambda x: x["name"])

    context = {
        "event": event,
        "present_participants": present_participants,
        "not_present_participants": not_present_participants,
        "total_participants": len(participants),
        "present_count": len(present_participants),
        "not_present_count": len(not_present_participants),
        "attendance_rate": (
            round((len(present_participants) / len(participants)) * 100, 1)
            if participants
            else 0
        ),
    }

    # If it's an AJAX request, return JSON data
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(
            {
                "present_participants": present_participants,
                "not_present_participants": not_present_participants,
                "present_count": len(present_participants),
                "not_present_count": len(not_present_participants),
                "total_participants": len(participants),
                "attendance_rate": context["attendance_rate"],
            }
        )

    return render(request, "attendance_dashboard.html", context)


@login_required
def export_attendance_csv(request, event_id):
    """
    Export attendance data as CSV with attendance status
    """
    import csv
    from django.utils import timezone

    event = get_object_or_404(Event, id=event_id)

    # Create filename as "attendance_output" with timestamp
    filename = f"attendance_output_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"

    # Create the HttpResponse object with CSV header and UTF-8 encoding
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    # Add UTF-8 BOM for better compatibility with Excel and other applications
    response.write("\ufeff")

    writer = csv.writer(response)

    # Write event name as the first row
    writer.writerow([f"Event: {event.event_name}"])
    writer.writerow([])  # Empty row for spacing

    # Write header row
    writer.writerow(
        [
            "Name",
            "Email",
            "Phone",
            "Attendance Status",
            "Registration Date",
            "Check-in Time",
            "Has Signature",
        ]
    )

    # Get all approved participants for this event
    participants = Participant.objects.filter(
        event=event, approval_status="approved"
    ).order_by("name")

    # Get attendance records
    attendance_records = Attendance.objects.filter(event=event).select_related(
        "participant"
    )
    attendance_dict = {att.participant.id: att for att in attendance_records}

    # Write participant data
    for participant in participants:
        attendance = attendance_dict.get(participant.id)

        attendance_status = (
            "Present" if attendance and attendance.present else "Not Present"
        )
        check_in_time = (
            attendance.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            if attendance and attendance.present
            else ""
        )
        has_signature = "Yes" if attendance and attendance.signature_file else "No"

        writer.writerow(
            [
                participant.name,
                participant.email,
                participant.phone or "",
                attendance_status,
                participant.registered_at.strftime("%Y-%m-%d %H:%M:%S"),
                check_in_time,
                has_signature,
            ]
        )

    return response


def scan_qr(request, event_id, participant_id):
    participant = get_object_or_404(Participant, id=participant_id, event_id=event_id)



@login_required
def export_event_rsvps_csv(request, event_id):
    """
    Export RSVP responses as CSV for an event. Includes all registered participants and their RSVP status (or 'No response').
    Optional querystring: ?filter=nonresponders to export only participants who have not replied.
    """
    import csv
    from django.utils import timezone

    event = get_object_or_404(Event, id=event_id)

    # Create filename with timestamp
    filter_param = request.GET.get("filter")
    filename_suffix = "nonresponders" if filter_param == "nonresponders" else "all_rsvps"
    filename = f"rsvp_responses_{filename_suffix}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    # Add BOM for Excel compatibility
    response.write("\ufeff")

    writer = csv.writer(response)

    # Header rows
    writer.writerow([f"Event: {event.event_name}"])
    writer.writerow([])
    writer.writerow([
        "Participant Name",
        "Email",
        "Phone",
        "Registered At",
        "RSVP Response",
        "RSVP Notes",
        "RSVP Date",
    ])

    # Get participants and RSVP responses for the event
    participants = Participant.objects.filter(event=event).order_by("name")
    rsvp_records = RSVPResponse.objects.filter(event=event).select_related("participant")
    rsvp_map = {r.participant_id: r for r in rsvp_records}

    for participant in participants:
        rsvp = rsvp_map.get(participant.id)

        if filter_param == "nonresponders" and rsvp:
            # skip those who responded
            continue

        response_val = rsvp.response if rsvp else "No response"
        notes_val = rsvp.notes if rsvp and rsvp.notes else ""
        rsvp_date_val = rsvp.response_date if rsvp else None

        # Format datetimes if present
        def _format_dt(v):
            if not v:
                return ""
            try:
                return v.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                return str(v)

        registered_at = participant.registered_at.strftime("%Y-%m-%d %H:%M:%S") if participant.registered_at else ""

        writer.writerow([
            participant.name,
            participant.email,
            participant.phone or "",
            registered_at,
            response_val,
            notes_val,
            _format_dt(rsvp_date_val),
        ])

    return response

    if request.user.is_authenticated:
        # Mark participant as present
        attendance, created = Attendance.objects.get_or_create(
            participant=participant, event=participant.event
        )
        attendance.present = True
        attendance.timestamp = now()
        attendance.save()

        messages.success(request, f"{participant.name} is marked as present.")
        return redirect("event_detail", event_id=event_id)

    else:
        return redirect("https://www.yoursite.com/unauthorized")
