from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Event, Participant, Attendance
from .forms import EventForm, ParticipantForm
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.timezone import now
from django.http import JsonResponse
import base64
from django.core.files.base import ContentFile


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
    events = Event.objects.all()
    return render(request, "events.html", {"events": events})


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
    print(event_id)
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
    """Handles QR code scan data and marks attendance."""
    if request.method == "POST":
        event_id = request.POST.get("event_id")
        participant_id = request.POST.get("participant_id")

        try:
            event = Event.objects.get(id=event_id)
            participant = Participant.objects.get(id=participant_id, event=event)
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
                    "present_count": Attendance.objects.filter(
                        event=event, present=True
                    ).count(),
                    "not_present_count": Participant.objects.filter(event=event)
                    .exclude(
                        id__in=Attendance.objects.filter(
                            event=event, present=True
                        ).values_list("participant_id", flat=True)
                    )
                    .count(),
                }
            )

        attendance.present = True
        attendance.timestamp = now()
        attendance.save()

        return JsonResponse(
            {
                "status": "success",
                "message": f"{participant.name} checked in successfully.",
                "participant_name": participant.name,
                "present_count": Attendance.objects.filter(
                    event=event, present=True
                ).count(),
                "not_present_count": Participant.objects.filter(event=event)
                .exclude(
                    id__in=Attendance.objects.filter(
                        event=event, present=True
                    ).values_list("participant_id", flat=True)
                )
                .count(),
            }
        )

    return JsonResponse({"status": "error", "message": "Invalid request."}, status=400)


def sign_signature(request, event_id, participant_id):
    """Serves the signature page and saves the signature."""

    event = get_object_or_404(Event, id=event_id)
    participant = get_object_or_404(Participant, id=participant_id, event=event)

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
        signature_file = ContentFile(
            base64.b64decode(imgstr),
            name=f"signatures/{participant.name}_{participant.id}.{ext}",
        )

        # Save the signature in the Attendance model
        attendance = get_object_or_404(Attendance, participant=participant, event=event)
        attendance.signature_file = signature_file
        attendance.save()

        return JsonResponse(
            {"status": "success", "message": "Signature saved successfully!"}
        )

    return render(
        request, "signature.html", {"event": event, "participant": participant}
    )
