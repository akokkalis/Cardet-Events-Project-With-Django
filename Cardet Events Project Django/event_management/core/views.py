from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Event, Participant, Attendance
from .forms import EventForm, ParticipantForm
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.timezone import now


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
        },
    )


def scan_qr(request, event_id, participant_id):
    participant = get_object_or_404(Participant, id=participant_id, event_id=event_id)

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
