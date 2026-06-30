from django.contrib.auth import authenticate
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token

from .models import Event, Participant, Staff
from .attendance import mark_attendance_for_participant


class IsStaffMember(IsAuthenticated):
    """Mirrors the login_view gate: token holder must be a superuser or have a Staff profile."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        user = request.user
        return user.is_superuser or Staff.objects.filter(user=user).exists()


class ApiLoginView(APIView):
    """
    Mobile app login: POST {username, password} → {"status": "success", "token": "..."}.
    Mirrors login_view's staff gate so only staff/superuser accounts can obtain a token.
    get_or_create means re-logging in returns the same token until ApiLogoutView invalidates it.
    One device can be shared by multiple staff members — each login gives back that user's token.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"status": "error", "message": "Username and password are required."},
                status=400,
            )

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {"status": "error", "message": "Invalid credentials."}, status=401
            )
        if not (user.is_superuser or Staff.objects.filter(user=user).exists()):
            return Response(
                {"status": "error", "message": "Not authorized for staff access."},
                status=403,
            )

        token, _ = Token.objects.get_or_create(user=user)
        return Response({"status": "success", "token": token.key})


class ApiLogoutView(APIView):
    """
    Invalidates the current token server-side so a staff member's explicit logout
    is permanent (not just forgotten on the device). The same user can re-authenticate
    via ApiLoginView and get a new token at any time.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.auth.delete()
        return Response({"status": "success"})


class MarkAttendanceAPIView(APIView):
    """
    Mobile-app-friendly attendance endpoint.

    Auth:     Authorization: Token <key>  (obtained via /api/login/)
    Body:     {"event_id": <int>, "participant_id": <int>}
    Response: same four shapes as the browser scan flow
              (status: error | warning | signature_required | success)
              so the mobile app can reuse the same handling code.

    IDs come from the existing QR format /scan_qr/{event_id}/{participant_id}/ —
    no QR regeneration needed.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsStaffMember]

    def post(self, request):
        event_id = request.data.get("event_id")
        participant_id = request.data.get("participant_id")

        if not event_id or not participant_id:
            return Response(
                {"status": "error", "message": "Invalid request."}, status=400
            )

        try:
            event = Event.objects.get(id=event_id)
            participant = Participant.objects.get(id=participant_id, event=event)
        except (Event.DoesNotExist, Participant.DoesNotExist):
            return Response(
                {"status": "error", "message": "Invalid QR code."}, status=400
            )

        body, status_code = mark_attendance_for_participant(event, participant)
        return Response(body, status=status_code)
