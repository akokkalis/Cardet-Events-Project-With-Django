from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from core.models import Event, Status
from datetime import datetime, time


class Command(BaseCommand):
    help = "Updates event statuses based on their dates"

    def handle(self, *args, **kwargs):
        today = timezone.now().date()

        # Get status objects
        try:
            completed_status = Status.objects.get(name="Completed")
            ongoing_status = Status.objects.get(name="Ongoing")
            cancelled_status = Status.objects.get(name="Cancelled")
        except Status.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    "❌ Required statuses not found. Please run ensure_event_statuses command first."
                )
            )
            return

        with transaction.atomic():
            # Get all events that are not cancelled
            events = Event.objects.exclude(status=cancelled_status)

            updated_count = 0
            for event in events:
                should_update = False
                new_status = None
                current_status_name = event.status.name if event.status else "No status"

                # If event date has passed
                if event.event_date < today:
                    new_status = completed_status
                    should_update = True
                # If event is today
                elif event.event_date == today:
                    # If end_time is set and has passed
                    if event.end_time and timezone.now().time() > event.end_time:
                        new_status = completed_status
                        should_update = True
                    # If it's ongoing
                    elif event.start_time:
                        if timezone.now().time() >= event.start_time:
                            new_status = ongoing_status
                            should_update = True

                if should_update and new_status and event.status != new_status:
                    event.status = new_status
                    event.save(update_fields=["status"])
                    updated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ Updated event "{event.event_name}": {current_status_name} → {new_status.name}'
                        )
                    )

        if updated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"✨ Successfully updated {updated_count} event(s)!")
            )
        else:
            self.stdout.write(self.style.SUCCESS("✓ No events needed updating."))
