#!/usr/bin/env python
"""
Test script for bulk certificate generation Celery task
"""

import os
import sys
import django

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "event_management.settings")
django.setup()

from core.tasks import bulk_generate_certificates_task
from core.models import Event, User


def test_bulk_certificate_generation():
    """Test the bulk certificate generation task"""

    print("🧪 Testing Bulk Certificate Generation Task")
    print("=" * 50)

    # Get the first event with a certificate template
    try:
        event = Event.objects.filter(certificate__isnull=False).first()
        if not event:
            print("❌ No events with certificate templates found")
            print("   Please create an event with a certificate template first")
            return False

        print(f"✅ Found event: {event.event_name}")
        print(f"   Certificate template: {event.certificate.name}")

        # Get the first user (admin)
        user = User.objects.first()
        if not user:
            print("❌ No users found")
            return False

        print(f"✅ Using user: {user.username}")

        # Get participant count
        participant_count = event.participant_set.count()
        print(f"✅ Participants to process: {participant_count}")

        if participant_count == 0:
            print("❌ No participants found for this event")
            print("   Please add some participants first")
            return False

        print("\n🚀 Starting bulk certificate generation task...")

        # Call the Celery task
        result = bulk_generate_certificates_task.delay(event.id, user.id)

        print(f"✅ Task queued successfully!")
        print(f"   Task ID: {result.id}")
        print(f"   Task Status: {result.status}")

        # Wait for the task to complete (for testing purposes)
        print("\n⏳ Waiting for task completion...")
        task_result = result.get(timeout=60)  # 60 second timeout

        print(f"✅ Task completed!")
        print(f"   Result: {task_result}")

        return True

    except Exception as e:
        print(f"❌ Error testing bulk certificate generation: {e}")
        return False


if __name__ == "__main__":
    print("🔧 Bulk Certificate Generation Task Test")
    print("=" * 50)

    success = test_bulk_certificate_generation()

    if success:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Tests failed!")
        sys.exit(1)
