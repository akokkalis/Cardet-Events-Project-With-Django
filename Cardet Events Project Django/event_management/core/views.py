from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Event, Participant, Attendance, Status
from .forms import EventForm, ParticipantForm
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.timezone import now
from django.http import JsonResponse, FileResponse, HttpResponse
import base64
from django.core.files.base import ContentFile
import os
from django.conf import settings
import zipfile


def login_view(request):
    """Handles staff login."""

    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)
        if user or user.is_staff:
            login(request, user)
            return redirect("event_list")  # Redirect to event list after login
        else:
            return render(
                request, "login.html", {"error": "Invalid username or password"}
            )

    return render(request, "login.html")


def logout_view(request):
    """Logs out the user."""
    logout(request)
    return redirect("login")


@login_required
def event_list(request):
    """Displays a list of events."""
    statuses = Status.objects.all()
    events = Event.objects.all()
    return render(request, "events.html", {"events": events, "statuses": statuses})


def filter_events(request):
    """Filter events dynamically via AJAX"""
    company_id = request.GET.get("company")
    status_id = request.GET.get("status")
    date = request.GET.get("date")

    events = Event.objects.all()

    if company_id:
        events = events.filter(company_id=company_id)

    if status_id:
        events = events.filter(status_id=status_id)

    if date:
        events = events.filter(event_date=date)

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
        }
        for event in events
    ]

    return JsonResponse({"events": event_list})


@login_required
def event_create(request):
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect("event_list")  # Redirect to events list after creation
    else:
        form = EventForm()

    return render(request, "event_form.html", {"form": form})


def event_edit(request, event_id):
    """Edit an existing event"""
    event = get_object_or_404(Event, id=event_id)

    if request.method == "POST":
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            return redirect("event_list")  # Redirect to the event list after editing
    else:
        form = EventForm(instance=event)

    return render(request, "event_edit.html", {"form": form, "event": event})


def event_delete(request, event_id):

    event = get_object_or_404(Event, id=event_id)
    event.delete()
    messages.success(request, "Event deleted successfully!")
    return redirect("event_list")


def event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    participants = Participant.objects.filter(event=event).order_by("name")
    present_participants = Attendance.objects.filter(
        event=event, present=True
    ).values_list("participant", flat=True)
    not_present_participants = participants.exclude(id__in=present_participants)

    for participant in participants:
        participant.attendance = Attendance.objects.filter(
            participant=participant, event=event
        ).first()

    if request.method == "POST":
        form = ParticipantForm(request.POST)
        if form.is_valid():
            # Check for duplicates
            if Participant.objects.filter(
                event=event, email=form.cleaned_data["email"]
            ).exists():
                messages.error(
                    request, "This participant is already registered for this event."
                )
            else:
                participant = form.save(commit=False)
                participant.event = event  # Assign event to participant
                participant.save()
                messages.success(
                    request, f"Participant {participant.name} added successfully."
                )
                return redirect(
                    "event_detail", event_id=event.id
                )  # Redirect to refresh page

    else:
        form = ParticipantForm()

    return render(
        request,
        "event_detail.html",
        {
            "event": event,
            "participants": participants,
            "form": form,
            "present_participants": participants.filter(id__in=present_participants),
            "not_present_participants": not_present_participants,
        },
    )


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

        return JsonResponse(
            {
                "status": "success",
                "message": f"{participant.name} checked in successfully.",
            }
        )

    return JsonResponse({"status": "error", "message": "Invalid request."}, status=400)


def signature_path(instance, filename):
    """Returns the correct path to store signatures inside the event folder."""
    return f"Events/{instance.event.id}_{instance.event.event_name.replace(' ', '_')}/signatures/{instance.participant.name}_{instance.participant.email.replace('@', '_').replace('.', '_')}_signature.png"


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

    # Serve the ZIP file for download
    zip_file = open(zip_path, "rb")
    response = FileResponse(zip_file, as_attachment=True, filename=zip_filename)

    return response
