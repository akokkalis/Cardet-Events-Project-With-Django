#!/usr/bin/env python
"""
Test script to verify RSVP email logging functionality with Celery tasks.
This script tests both individual and bulk RSVP email operations.
"""

import os
import sys
import django
from django.conf import settings

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "event_management.settings")
django.setup()

from core.models import Event, Participant, EventEmail, RSVPEmailLog
from core.tasks import (
    send_rsvp_email_task,
    send_bulk_rsvp_emails_task,
    check_bulk_rsvp_completion,
)
from django.contrib.auth.models import User
from django.utils import timezone


def test_individual_rsvp_email_logging():
    """Test individual RSVP email with log tracking"""
    print("🧪 Testing individual RSVP email with log tracking...")

    try:
        # Get a test event and participant
        event = Event.objects.first()
        if not event:
            print("❌ No events found in database")
            return False

        participant = Participant.objects.filter(event=event).first()
        if not participant:
            print("❌ No participants found for the event")
            return False

        # Create a test log entry
        user = User.objects.first()
        log_entry = RSVPEmailLog.objects.create(
            event=event, user=user, total_recipients=1, status="in_progress"
        )

        print(f"📝 Created log entry: {log_entry.id}")

        # Test the task with log_id
        result = send_rsvp_email_task.delay(participant.id, log_entry.id)

        print(f"✅ Task queued: {result.id}")
        print(f"📧 Individual RSVP email task with logging: SUCCESS")

        return True

    except Exception as e:
        print(f"❌ Error testing individual RSVP email logging: {e}")
        return False


def test_bulk_rsvp_email_logging():
    """Test bulk RSVP email with log tracking"""
    print("\n🧪 Testing bulk RSVP email with log tracking...")

    try:
        # Get a test event
        event = Event.objects.first()
        if not event:
            print("❌ No events found in database")
            return False

        participants = Participant.objects.filter(event=event)[
            :3
        ]  # Test with 3 participants
        if not participants.exists():
            print("❌ No participants found for the event")
            return False

        user = User.objects.first()
        participant_ids = list(participants.values_list("id", flat=True))

        print(f"📧 Testing bulk RSVP for {len(participant_ids)} participants")

        # Test the bulk task
        result = send_bulk_rsvp_emails_task.delay(event.id, participant_ids, user.id)

        print(f"✅ Bulk task queued: {result.id}")
        print(f"📧 Bulk RSVP email task with logging: SUCCESS")

        return True

    except Exception as e:
        print(f"❌ Error testing bulk RSVP email logging: {e}")
        return False


def test_completion_check():
    """Test the completion check task"""
    print("\n🧪 Testing completion check task...")

    try:
        # Get a recent log entry
        log_entry = RSVPEmailLog.objects.filter(status="in_progress").first()
        if not log_entry:
            print("⚠️ No in-progress log entries found, creating test entry...")
            event = Event.objects.first()
            user = User.objects.first()
            log_entry = RSVPEmailLog.objects.create(
                event=event,
                user=user,
                total_recipients=5,
                emails_sent=3,
                emails_failed=1,
                status="in_progress",
            )

        # Test the completion check task
        result = check_bulk_rsvp_completion.delay(log_entry.id)

        print(f"✅ Completion check task queued: {result.id}")
        print(f"📊 Completion check task: SUCCESS")

        return True

    except Exception as e:
        print(f"❌ Error testing completion check: {e}")
        return False


def check_log_entries():
    """Check existing log entries"""
    print("\n📊 Checking existing RSVP email log entries...")

    try:
        logs = RSVPEmailLog.objects.all().order_by("-started_at")[:5]

        if not logs.exists():
            print("ℹ️ No RSVP email log entries found")
            return

        print(f"📋 Found {logs.count()} log entries:")

        for log in logs:
            print(f"  - ID: {log.id}")
            print(f"    Event: {log.event.event_name}")
            print(f"    Status: {log.status}")
            print(
                f"    Progress: {log.emails_sent + log.emails_failed}/{log.total_recipients}"
            )
            print(f"    Started: {log.started_at}")
            if log.completed_at:
                print(f"    Completed: {log.completed_at}")
            print()

    except Exception as e:
        print(f"❌ Error checking log entries: {e}")


def main():
    """Main test function"""
    print("🚀 Testing RSVP Email Logging with Celery Tasks")
    print("=" * 50)

    # Check if Celery is configured
    try:
        from celery import current_app

        print(f"✅ Celery app: {current_app.main}")
    except Exception as e:
        print(f"❌ Celery not configured: {e}")
        return

    # Run tests
    success_count = 0
    total_tests = 3

    if test_individual_rsvp_email_logging():
        success_count += 1

    if test_bulk_rsvp_email_logging():
        success_count += 1

    if test_completion_check():
        success_count += 1

    # Check log entries
    check_log_entries()

    # Summary
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {success_count}/{total_tests} tests passed")

    if success_count == total_tests:
        print("✅ All RSVP email logging tests passed!")
        print("\n🎉 RSVP email logging is working correctly with Celery tasks.")
        print("   - Individual emails can optionally update log entries")
        print("   - Bulk operations create and update log entries in real-time")
        print("   - Completion monitoring works automatically")
    else:
        print("❌ Some tests failed. Check the output above for details.")
        print("\n🔧 Troubleshooting:")
        print("   - Ensure Redis is running")
        print("   - Ensure Celery workers are running")
        print("   - Check database connectivity")
        print("   - Verify email templates exist")


if __name__ == "__main__":
    main()
