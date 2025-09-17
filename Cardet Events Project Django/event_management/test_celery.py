#!/usr/bin/env python
"""
Simple test script to verify Celery tasks are working.
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

from core.tasks import (
    test_hello,
    send_ticket_email_task,
    process_registration_task,
    process_approval_task,
    process_rejection_task,
)


def test_celery_tasks():
    """Test that Celery tasks can be queued and executed."""

    print("🧪 Testing Celery tasks...")

    # Test the simple hello task
    print("1. Testing test_hello task...")
    try:
        result = test_hello.delay("World")
        print(f"   ✅ Task queued with ID: {result.id}")

        # Wait for the result
        task_result = result.get(timeout=10)
        print(f"   ✅ Task completed: {task_result}")

    except Exception as e:
        print(f"   ❌ Error testing hello task: {e}")
        return False

        print("2. Testing ticket email task (with invalid participant ID)...")
    try:
        # Test with an invalid participant ID to see error handling
        result = send_ticket_email_task.delay(99999)  # Non-existent participant
        print(f"   ✅ Task queued with ID: {result.id}")

        # Wait for the result
        task_result = result.get(timeout=10)
        print(f"   ✅ Task completed with expected error: {task_result}")

    except Exception as e:
        print(f"   ❌ Error testing ticket email task: {e}")
        return False

    print("3. Testing process registration task (with invalid participant ID)...")
    try:
        # Test with an invalid participant ID to see error handling
        result = process_registration_task.delay(99999)  # Non-existent participant
        print(f"   ✅ Task queued with ID: {result.id}")

        # Wait for the result
        task_result = result.get(timeout=10)
        print(f"   ✅ Task completed with expected error: {task_result}")

    except Exception as e:
        print(f"   ❌ Error testing process registration task: {e}")
        return False

    print("4. Testing process approval task (with invalid participant ID)...")
    try:
        # Test with an invalid participant ID to see error handling
        result = process_approval_task.delay(99999)  # Non-existent participant
        print(f"   ✅ Task queued with ID: {result.id}")

        # Wait for the result
        task_result = result.get(timeout=10)
        print(f"   ✅ Task completed with expected error: {task_result}")

    except Exception as e:
        print(f"   ❌ Error testing process approval task: {e}")
        return False

    print("5. Testing process rejection task (with invalid participant ID)...")
    try:
        # Test with an invalid participant ID to see error handling
        result = process_rejection_task.delay(99999)  # Non-existent participant
        print(f"   ✅ Task queued with ID: {result.id}")

        # Wait for the result
        task_result = result.get(timeout=10)
        print(f"   ✅ Task completed with expected error: {task_result}")

    except Exception as e:
        print(f"   ❌ Error testing process rejection task: {e}")
        return False

    print("🎉 All Celery task tests passed!")
    return True


if __name__ == "__main__":
    success = test_celery_tasks()
    sys.exit(0 if success else 1)
