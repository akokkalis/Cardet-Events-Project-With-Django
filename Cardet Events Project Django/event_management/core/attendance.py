from django.utils.timezone import now
from .models import Attendance, Participant


def mark_attendance_for_participant(event, participant):
    """
    Shared attendance-marking logic used by both the session-based web view
    (core.views.mark_attendance) and the token-based mobile API
    (core.api_views.MarkAttendanceAPIView). Returns (response_dict, http_status).
    Response shapes match exactly what the browser UI already expects, so the
    mobile app can reuse the same handling code as the web scan page.
    """
    if participant.approval_status != "approved":
        return (
            {
                "status": "error",
                "message": "Invalid ticket. Participant is not approved for this event.",
                "participant_name": participant.name,
                "participant_approval_status": participant.approval_status,
            },
            400,
        )

    attendance, created = Attendance.objects.get_or_create(
        participant=participant, event=event
    )
    if attendance.present:
        return (
            {
                "status": "warning",
                "message": f"{participant.name} is already checked in!",
                "participant_name": participant.name,
                "participant_approval_status": participant.approval_status,
            },
            200,
        )

    attendance.present = True
    attendance.timestamp = now()
    attendance.save()

    if event.signatures:
        return (
            {
                "status": "signature_required",
                "redirect_url": f"/sign_signature/{event.id}/{participant.id}/",
            },
            200,
        )

    total_present = Attendance.objects.filter(
        event=event, present=True, participant__approval_status="approved"
    ).count()
    total_registered = Participant.objects.filter(
        event=event, approval_status="approved"
    ).count()
    not_present = total_registered - total_present

    return (
        {
            "status": "success",
            "message": f"{participant.name} checked in successfully.",
            "participant_name": participant.name,
            "participant_approval_status": participant.approval_status,
            "present_count": total_present,
            "not_present_count": not_present,
        },
        200,
    )
