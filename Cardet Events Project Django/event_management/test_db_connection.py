#!/usr/bin/env python
"""
Test script to verify database connectivity and participant data.
Run this from the Django project directory.
"""

import os
import sys
import django

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "event_management.settings")
django.setup()

from core.models import Participant
from core.tasks import test_database_connection


def test_database():
    """Test database connectivity and participant data."""

    print("🧪 Testing database connectivity...")

    try:
        # Test basic database connection
        total_participants = Participant.objects.count()
        print(
            f"✅ Database connection successful. Total participants: {total_participants}"
        )

        if total_participants > 0:
            # Show first 5 participants
            print("\n📋 First 5 participants:")
            for participant in Participant.objects.all()[:5]:
                print(
                    f"   ID: {participant.id}, Name: {participant.name}, Email: {participant.email}"
                )

            # Test specific participant lookup
            try:
                participant_3 = Participant.objects.get(id=3)
                print(
                    f"\n✅ Participant with ID 3 found: {participant_3.name} ({participant_3.email})"
                )
            except Participant.DoesNotExist:
                print(f"\n❌ Participant with ID 3 not found")

                # Show available IDs
                available_ids = list(
                    Participant.objects.values_list("id", flat=True)[:10]
                )
                print(f"   Available participant IDs: {available_ids}")
        else:
            print("❌ No participants found in database")

    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False

    return True


def test_celery_database():
    """Test database connectivity through Celery task."""

    print("\n🧪 Testing Celery database connectivity...")

    try:
        # Queue the test task
        result = test_database_connection.delay()
        print(f"✅ Test task queued with ID: {result.id}")

        # Wait for the result
        task_result = result.get(timeout=30)
        print(f"✅ Celery task completed: {task_result}")

        return task_result.get("status") == "success"

    except Exception as e:
        print(f"❌ Error testing Celery database connection: {e}")
        return False


if __name__ == "__main__":
    print("🔍 Database and Celery Connection Test")
    print("=" * 50)

    # Test direct database connection
    db_success = test_database()

    # Test Celery database connection
    celery_success = test_celery_database()

    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print(f"   Direct Database: {'✅ PASS' if db_success else '❌ FAIL'}")
    print(f"   Celery Database: {'✅ PASS' if celery_success else '❌ FAIL'}")

    if db_success and celery_success:
        print("\n🎉 All tests passed! Database connectivity is working correctly.")
    else:
        print("\n⚠️ Some tests failed. Check the output above for details.")
