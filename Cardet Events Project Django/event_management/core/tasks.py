from celery import shared_task
import time


@shared_task
def test_hello(name):
    print(f"Hello, {name}! Task is running.")

    for i in range(10):
        print(f"Hello, {name}! Task is running. {i}")

    return f"Task completed for {name}"
