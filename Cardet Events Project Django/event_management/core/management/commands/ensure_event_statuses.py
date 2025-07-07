from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Status


class Command(BaseCommand):
    help = "Ensures that all required event statuses exist in the database"

    def handle(self, *args, **kwargs):
        # Define the required statuses with their properties
        required_statuses = [
            {"name": "Planned", "color": "#3498db", "priority": 1},  # Blue
            {"name": "Ongoing", "color": "#f1c40f", "priority": 2},  # Yellow
            {"name": "Completed", "color": "#2ecc71", "priority": 3},  # Green
            {"name": "Cancelled", "color": "#e74c3c", "priority": 4},  # Red
        ]

        with transaction.atomic():
            for status_data in required_statuses:
                status, created = Status.objects.get_or_create(
                    name=status_data["name"],
                    defaults={
                        "color": status_data["color"],
                        "priority": status_data["priority"],
                    },
                )

                if created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ Created status "{status.name}" with color {status.color}'
                        )
                    )
                else:
                    # Update color and priority if they differ
                    if (
                        status.color != status_data["color"]
                        or status.priority != status_data["priority"]
                    ):
                        status.color = status_data["color"]
                        status.priority = status_data["priority"]
                        status.save()
                        self.stdout.write(
                            self.style.WARNING(
                                f'🔄 Updated status "{status.name}" with new color/priority'
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✓ Status "{status.name}" already exists'
                            )
                        )

        self.stdout.write(
            self.style.SUCCESS("✨ All required event statuses are in place!")
        )
