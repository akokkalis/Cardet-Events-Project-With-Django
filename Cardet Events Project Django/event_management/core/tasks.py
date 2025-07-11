from celery import shared_task
import time
import os
from django.core.mail import EmailMessage, get_connection
from django.utils.html import strip_tags
from django.template import Template, Context
from .models import Participant, EventEmail
from .utils import email_body, generate_rsvp_urls
from datetime import date, timedelta


@shared_task
def test_hello(name):
    print(f"Hello, {name}! Task is running.")

    for i in range(10):
        print(f"Hello, {name}! Task is running. {i}")

    return f"Task completed for {name}"


@shared_task
def test_database_connection():
    """Test task to verify database connectivity in Celery workers."""
    try:
        # Test basic database connection
        total_participants = Participant.objects.count()
        print(
            f"✅ Database connection successful. Total participants: {total_participants}"
        )

        # Test specific participant lookup
        if total_participants > 0:
            first_participant = Participant.objects.first()
            print(
                f"✅ First participant: ID={first_participant.id}, Name={first_participant.name}"
            )

            # Test participant with ID 3 specifically
            try:
                participant_3 = Participant.objects.get(id=3)
                print(f"✅ Participant with ID 3 found: {participant_3.name}")
                return {
                    "status": "success",
                    "message": f"Database connection working. Participant 3: {participant_3.name}",
                    "total_participants": total_participants,
                }
            except Participant.DoesNotExist:
                print(f"❌ Participant with ID 3 not found")
                return {
                    "status": "error",
                    "message": "Participant with ID 3 not found in database",
                    "total_participants": total_participants,
                }
        else:
            print("❌ No participants found in database")
            return {
                "status": "error",
                "message": "No participants found in database",
                "total_participants": 0,
            }

    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return {"status": "error", "message": f"Database connection failed: {str(e)}"}


@shared_task
def send_ticket_email_task(participant_id):
    """
    Celery task to send ticket email to a participant.
    This replaces the threading approach in send_ticket_email_view.
    """
    try:
        from .models import RSVPEmailLog
        from django.contrib.auth.models import User
        from django.utils import timezone

        # Get the participant
        participant = Participant.objects.get(id=participant_id)

        # Create email log for tracking
        user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        email_log = RSVPEmailLog.objects.create(
            event=participant.event,
            user=user,
            status="in_progress",
            total_recipients=1,
            emails_sent=0,
            emails_failed=0,
        )

        # Ensure event requires tickets and participant has a ticket
        if not participant.event.tickets or not participant.pdf_ticket:
            print(
                f"❌ Event does not require tickets or no ticket found for participant {participant_id}"
            )
            return {
                "status": "error",
                "message": "This event does not require tickets or no ticket found.",
            }

        # Get company email configuration
        email_config = getattr(participant.event.company, "email_config", None)
        if not email_config:
            print(
                f"❌ No email configuration found for company {participant.event.company.name}"
            )
            return {
                "status": "error",
                "message": "No email configuration found for this company.",
            }

        # Email subject & event information
        subject = f"Your Ticket for {participant.event.event_name}"
        event_info = {
            "title": participant.event.event_name,
            "location": participant.event.location,
            "date": participant.event.event_date.strftime("%d-%m-%y"),
            "starttime": (
                participant.event.start_time.strftime("%H:%M")
                if participant.event.start_time
                else "TBA"
            ),
            "endtime": (
                participant.event.end_time.strftime("%H:%M")
                if participant.event.end_time
                else "TBA"
            ),
            "company_email": participant.event.company.email,
        }

        # Generate email body with correct parameters
        html_message = email_body(participant.name, event_info)
        plain_message = strip_tags(
            html_message
        )  # Remove HTML tags for plaintext fallback

        # Get PDF Ticket Path
        pdf_path = participant.pdf_ticket.path if participant.pdf_ticket else None

        # Create SMTP connection
        connection = get_connection(
            host=email_config.smtp_server,
            port=email_config.smtp_port,
            username=email_config.email_address,
            password=email_config.email_password,
            use_tls=email_config.use_tls,
            use_ssl=email_config.use_ssl,
        )

        # Send the email
        email = EmailMessage(
            subject,
            html_message,
            from_email=email_config.email_address,
            to=[participant.email],
            connection=connection,
        )
        email.content_subtype = "html"  # Ensure HTML email formatting

        # Attach the ticket if available
        if pdf_path and os.path.exists(pdf_path):
            email.attach_file(pdf_path)

        email.send()
        print(f"✅ Ticket email sent to {participant.email} via Celery task")

        # Log success
        email_log.status = "completed"
        email_log.emails_sent = 1
        email_log.log_messages.append(
            {
                "type": "success",
                "timestamp": timezone.now().isoformat(),
                "message": f"Successfully sent ticket email to {participant.email}",
                "participant": f"{participant.name} ({participant.email})",
                "email_type": "ticket",
                "subject": subject,
            }
        )
        email_log.completed_at = timezone.now()
        email_log.save()

        return {
            "status": "success",
            "message": f"Ticket sent successfully to {participant.email}!",
        }

    except Participant.DoesNotExist:
        print(f"❌ Participant with ID {participant_id} not found")
        if "email_log" in locals():
            email_log.status = "failed"
            email_log.emails_failed = 1
            email_log.log_messages.append(
                {
                    "type": "error",
                    "timestamp": timezone.now().isoformat(),
                    "message": "Participant not found",
                    "participant": f"ID: {participant_id}",
                    "email_type": "ticket",
                }
            )
            email_log.completed_at = timezone.now()
            email_log.save()
        return {"status": "error", "message": "Participant not found."}
    except Exception as e:
        print(f"❌ Error sending email to participant {participant_id}: {e}")
        if "email_log" in locals():
            email_log.status = "failed"
            email_log.emails_failed = 1
            email_log.log_messages.append(
                {
                    "type": "error",
                    "timestamp": timezone.now().isoformat(),
                    "message": f"Error sending ticket email: {str(e)}",
                    "participant": f"ID: {participant_id}",
                    "email_type": "ticket",
                    "error_details": str(e),
                }
            )
            email_log.completed_at = timezone.now()
            email_log.save()
        return {"status": "error", "message": f"Error sending email: {str(e)}"}


@shared_task
def send_approval_email_task(participant_id):
    """
    Celery task to send approval email to a participant.
    This replaces the threading approach in signals.py.
    """
    try:
        from .models import RSVPEmailLog
        from django.contrib.auth.models import User
        from django.utils import timezone

        participant = Participant.objects.get(id=participant_id)

        # Create email log for tracking
        user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        email_log = RSVPEmailLog.objects.create(
            event=participant.event,
            user=user,
            status="in_progress",
            total_recipients=1,
            emails_sent=0,
            emails_failed=0,
        )

        # Get the event's approval email template
        try:
            event_email = EventEmail.objects.get(
                event=participant.event, reason="approval"
            )
        except EventEmail.DoesNotExist:
            print(
                f"📧 No approval email template found for {participant.event.event_name}"
            )
            return {"status": "error", "message": "No approval email template found."}

        # Get company email configuration
        email_config = getattr(participant.event.company, "email_config", None)
        if not email_config:
            print(
                f"⚠️ No email configuration found for {participant.event.company.name}"
            )
            return {
                "status": "error",
                "message": "No email configuration found for this company.",
            }

        # Prepare template context with placeholders
        context_data = {
            "name": participant.name,
            "event_name": participant.event.event_name,
            "event_date": participant.event.event_date.strftime("%B %d, %Y"),
            "event_location": participant.event.location or "TBA",
            "start_time": (
                participant.event.start_time.strftime("%I:%M %p")
                if participant.event.start_time
                else "TBA"
            ),
            "end_time": (
                participant.event.end_time.strftime("%I:%M %p")
                if participant.event.end_time
                else "TBA"
            ),
            "email": participant.email,
            "phone": participant.phone or "N/A",
        }

        # Add RSVP URLs to context for all email templates
        rsvp_urls = generate_rsvp_urls(participant)
        context_data.update(rsvp_urls)

        # Render the email subject and body with template placeholders
        subject_template = Template(event_email.subject)
        body_template = Template(event_email.body)
        context = Context(context_data)

        rendered_subject = subject_template.render(context)
        rendered_body = body_template.render(context)

        # Create the SMTP connection
        connection = get_connection(
            host=email_config.smtp_server,
            port=email_config.smtp_port,
            username=email_config.email_address,
            password=email_config.email_password,
            use_tls=email_config.use_tls,
            use_ssl=email_config.use_ssl,
        )

        # Send the email
        email = EmailMessage(
            rendered_subject,
            rendered_body,
            from_email=email_config.email_address,
            to=[participant.email],
            connection=connection,
        )
        email.content_subtype = "html"  # Support HTML in email templates
        email.send()

        print(
            f"✅ Approval email sent to {participant.email} for {participant.event.event_name} via Celery task"
        )

        # Log success
        email_log.status = "completed"
        email_log.emails_sent = 1
        email_log.log_messages.append(
            {
                "type": "success",
                "timestamp": timezone.now().isoformat(),
                "message": f"Successfully sent approval email to {participant.email}",
                "participant": f"{participant.name} ({participant.email})",
                "email_type": "approval",
                "subject": rendered_subject,
                "template_used": "approval",
            }
        )
        email_log.completed_at = timezone.now()
        email_log.save()

        return {
            "status": "success",
            "message": f"Approval email sent successfully to {participant.email}!",
        }

    except Participant.DoesNotExist:
        print(f"❌ Participant with ID {participant_id} not found")
        if "email_log" in locals():
            email_log.status = "failed"
            email_log.emails_failed = 1
            email_log.log_messages.append(
                {
                    "type": "error",
                    "timestamp": timezone.now().isoformat(),
                    "message": "Participant not found",
                    "participant": f"ID: {participant_id}",
                    "email_type": "approval",
                }
            )
            email_log.completed_at = timezone.now()
            email_log.save()
        return {"status": "error", "message": "Participant not found."}
    except Exception as e:
        print(f"❌ Error sending approval email to participant {participant_id}: {e}")
        if "email_log" in locals():
            email_log.status = "failed"
            email_log.emails_failed = 1
            email_log.log_messages.append(
                {
                    "type": "error",
                    "timestamp": timezone.now().isoformat(),
                    "message": f"Error sending approval email: {str(e)}",
                    "participant": f"ID: {participant_id}",
                    "email_type": "approval",
                    "error_details": str(e),
                }
            )
            email_log.completed_at = timezone.now()
            email_log.save()
        return {"status": "error", "message": f"Error sending approval email: {str(e)}"}


@shared_task
def send_rejection_email_task(participant_id):
    """
    Celery task to send rejection email to a participant.
    This replaces the threading approach in signals.py.
    """
    try:
        participant = Participant.objects.get(id=participant_id)

        # Get the event's rejection email template
        try:
            event_email = EventEmail.objects.get(
                event=participant.event, reason="rejection"
            )
        except EventEmail.DoesNotExist:
            print(
                f"📧 No rejection email template found for {participant.event.event_name}"
            )
            return {"status": "error", "message": "No rejection email template found."}

        # Get company email configuration
        email_config = getattr(participant.event.company, "email_config", None)
        if not email_config:
            print(
                f"⚠️ No email configuration found for {participant.event.company.name}"
            )
            return {
                "status": "error",
                "message": "No email configuration found for this company.",
            }

        # Prepare template context with placeholders
        context_data = {
            "name": participant.name,
            "event_name": participant.event.event_name,
            "event_date": participant.event.event_date.strftime("%B %d, %Y"),
            "event_location": participant.event.location or "TBA",
            "start_time": (
                participant.event.start_time.strftime("%I:%M %p")
                if participant.event.start_time
                else "TBA"
            ),
            "end_time": (
                participant.event.end_time.strftime("%I:%M %p")
                if participant.event.end_time
                else "TBA"
            ),
            "email": participant.email,
            "phone": participant.phone or "N/A",
        }

        # Add RSVP URLs to context for all email templates
        rsvp_urls = generate_rsvp_urls(participant)
        context_data.update(rsvp_urls)

        # Render the email subject and body with template placeholders
        subject_template = Template(event_email.subject)
        body_template = Template(event_email.body)
        context = Context(context_data)

        rendered_subject = subject_template.render(context)
        rendered_body = body_template.render(context)

        # Create the SMTP connection
        connection = get_connection(
            host=email_config.smtp_server,
            port=email_config.smtp_port,
            username=email_config.email_address,
            password=email_config.email_password,
            use_tls=email_config.use_tls,
            use_ssl=email_config.use_ssl,
        )

        # Send the email
        email = EmailMessage(
            rendered_subject,
            rendered_body,
            from_email=email_config.email_address,
            to=[participant.email],
            connection=connection,
        )
        email.content_subtype = "html"  # Support HTML in email templates
        email.send()

        print(
            f"✅ Rejection email sent to {participant.email} for {participant.event.event_name} via Celery task"
        )

        return {
            "status": "success",
            "message": f"Rejection email sent successfully to {participant.email}!",
        }

    except Participant.DoesNotExist:
        print(f"❌ Participant with ID {participant_id} not found")
        return {"status": "error", "message": "Participant not found."}
    except Exception as e:
        print(f"❌ Error sending rejection email to participant {participant_id}: {e}")
        return {
            "status": "error",
            "message": f"Error sending rejection email: {str(e)}",
        }


@shared_task
def send_registration_email_task(participant_id):
    """
    Celery task to send registration confirmation email to a participant.
    This replaces the threading approach in signals.py.
    """
    try:
        participant = Participant.objects.get(id=participant_id)

        # Get the event's registration email template
        try:
            event_email = EventEmail.objects.get(
                event=participant.event, reason="registration"
            )
        except EventEmail.DoesNotExist:
            print(
                f"📧 No registration email template found for {participant.event.event_name}"
            )
            return {
                "status": "error",
                "message": "No registration email template found.",
            }

        # Get company email configuration
        email_config = getattr(participant.event.company, "email_config", None)
        if not email_config:
            print(
                f"⚠️ No email configuration found for {participant.event.company.name}"
            )
            return {
                "status": "error",
                "message": "No email configuration found for this company.",
            }

        # Prepare template context with placeholders
        context_data = {
            "name": participant.name,
            "event_name": participant.event.event_name,
            "event_date": participant.event.event_date.strftime("%B %d, %Y"),
            "event_location": participant.event.location or "TBA",
            "start_time": (
                participant.event.start_time.strftime("%I:%M %p")
                if participant.event.start_time
                else "TBA"
            ),
            "end_time": (
                participant.event.end_time.strftime("%I:%M %p")
                if participant.event.end_time
                else "TBA"
            ),
            "email": participant.email,
            "phone": participant.phone or "N/A",
        }

        # Add RSVP URLs to context for all email templates
        rsvp_urls = generate_rsvp_urls(participant)
        context_data.update(rsvp_urls)

        # Render the email subject and body with template placeholders
        subject_template = Template(event_email.subject)
        body_template = Template(event_email.body)
        context = Context(context_data)

        rendered_subject = subject_template.render(context)
        rendered_body = body_template.render(context)

        # Create the SMTP connection
        connection = get_connection(
            host=email_config.smtp_server,
            port=email_config.smtp_port,
            username=email_config.email_address,
            password=email_config.email_password,
            use_tls=email_config.use_tls,
            use_ssl=email_config.use_ssl,
        )

        # Send the email
        email = EmailMessage(
            rendered_subject,
            rendered_body,
            from_email=email_config.email_address,
            to=[participant.email],
            connection=connection,
        )
        email.content_subtype = "html"  # Support HTML in email templates
        email.send()

        print(
            f"✅ Registration email sent to {participant.email} for {participant.event.event_name} via Celery task"
        )

        return {
            "status": "success",
            "message": f"Registration email sent successfully to {participant.email}!",
        }

    except Participant.DoesNotExist:
        print(f"❌ Participant with ID {participant_id} not found")
        return {"status": "error", "message": "Participant not found."}
    except Exception as e:
        print(
            f"❌ Error sending registration email to participant {participant_id}: {e}"
        )
        return {
            "status": "error",
            "message": f"Error sending registration email: {str(e)}",
        }


@shared_task
def send_rsvp_email_task(participant_id, log_id=None):
    """
    Celery task to send RSVP email to a participant.
    This replaces the threading approach in signals.py.
    """
    from .models import RSVPEmailLog
    from django.utils import timezone

    try:
        participant = Participant.objects.get(id=participant_id)

        # Get the event's RSVP email template
        try:
            event_email = EventEmail.objects.get(event=participant.event, reason="rsvp")
        except EventEmail.DoesNotExist:
            print(f"📧 No RSVP email template found for {participant.event.event_name}")
            if log_id:
                try:
                    email_log = RSVPEmailLog.objects.get(id=log_id)
                    email_log.emails_failed += 1
                    email_log.log_messages.append(
                        {
                            "type": "error",
                            "timestamp": timezone.now().isoformat(),
                            "message": "No RSVP email template found.",
                            "participant": f"ID: {participant_id}",
                            "email_type": "rsvp",
                        }
                    )
                    email_log.save()
                except RSVPEmailLog.DoesNotExist:
                    print(f"⚠️ RSVPEmailLog with ID {log_id} not found")
            return {"status": "error", "message": "No RSVP email template found."}

        # Get company email configuration
        email_config = getattr(participant.event.company, "email_config", None)
        if not email_config:
            print(
                f"⚠️ No email configuration found for {participant.event.company.name}"
            )
            if log_id:
                try:
                    email_log = RSVPEmailLog.objects.get(id=log_id)
                    email_log.emails_failed += 1
                    email_log.log_messages.append(
                        {
                            "type": "error",
                            "timestamp": timezone.now().isoformat(),
                            "message": "No email configuration found for this company.",
                            "participant": f"ID: {participant_id}",
                            "email_type": "rsvp",
                        }
                    )
                    email_log.save()
                except RSVPEmailLog.DoesNotExist:
                    print(f"⚠️ RSVPEmailLog with ID {log_id} not found")
            return {
                "status": "error",
                "message": "No email configuration found for this company.",
            }

        # Prepare template context with placeholders
        context_data = {
            "name": participant.name,
            "event_name": participant.event.event_name,
            "event_date": participant.event.event_date.strftime("%B %d, %Y"),
            "event_location": participant.event.location or "TBA",
            "start_time": (
                participant.event.start_time.strftime("%I:%M %p")
                if participant.event.start_time
                else "TBA"
            ),
            "end_time": (
                participant.event.end_time.strftime("%I:%M %p")
                if participant.event.end_time
                else "TBA"
            ),
            "email": participant.email,
            "phone": participant.phone or "N/A",
        }

        # Add RSVP URLs to context for all email templates
        rsvp_urls = generate_rsvp_urls(participant)
        context_data.update(rsvp_urls)

        # Render the email subject and body with template placeholders
        subject_template = Template(event_email.subject)
        body_template = Template(event_email.body)
        context = Context(context_data)

        rendered_subject = subject_template.render(context)
        rendered_body = body_template.render(context)

        # Create the SMTP connection
        connection = get_connection(
            host=email_config.smtp_server,
            port=email_config.smtp_port,
            username=email_config.email_address,
            password=email_config.email_password,
            use_tls=email_config.use_tls,
            use_ssl=email_config.use_ssl,
        )

        # Send the email (only increment failed if this fails)
        try:
            email = EmailMessage(
                rendered_subject,
                rendered_body,
                from_email=email_config.email_address,
                to=[participant.email],
                connection=connection,
            )
            email.content_subtype = "html"  # Support HTML in email templates
            email.send()
            print(
                f"✅ RSVP email sent to {participant.email} for {participant.event.event_name} via Celery task"
            )
            if log_id:
                try:
                    email_log = RSVPEmailLog.objects.get(id=log_id)
                    email_log.emails_sent += 1
                    email_log.log_messages.append(
                        {
                            "type": "success",
                            "timestamp": timezone.now().isoformat(),
                            "message": f"Successfully sent RSVP email to {participant.email}",
                            "participant": f"{participant.name} ({participant.email})",
                            "email_type": "rsvp",
                            "subject": rendered_subject,
                            "template_used": "rsvp",
                        }
                    )
                    email_log.save()
                except RSVPEmailLog.DoesNotExist:
                    print(f"⚠️ RSVPEmailLog with ID {log_id} not found")
            return {
                "status": "success",
                "message": f"RSVP email sent successfully to {participant.email}!",
            }
        except Exception as e:
            print(f"❌ Error sending RSVP email to participant {participant_id}: {e}")
            if log_id:
                try:
                    email_log = RSVPEmailLog.objects.get(id=log_id)
                    email_log.emails_failed += 1
                    email_log.log_messages.append(
                        {
                            "type": "error",
                            "timestamp": timezone.now().isoformat(),
                            "message": f"Error sending RSVP email: {str(e)}",
                            "participant": f"ID: {participant_id}",
                            "email_type": "rsvp",
                            "error_details": str(e),
                        }
                    )
                    email_log.save()
                except RSVPEmailLog.DoesNotExist:
                    print(f"⚠️ RSVPEmailLog with ID {log_id} not found")
            return {"status": "error", "message": f"Error sending RSVP email: {str(e)}"}

    except Participant.DoesNotExist:
        print(f"❌ Participant with ID {participant_id} not found")
        if log_id:
            try:
                email_log = RSVPEmailLog.objects.get(id=log_id)
                email_log.emails_failed += 1
                email_log.log_messages.append(
                    {
                        "type": "error",
                        "timestamp": timezone.now().isoformat(),
                        "message": "Participant not found.",
                        "participant": f"ID: {participant_id}",
                        "email_type": "rsvp",
                    }
                )
                email_log.save()
            except RSVPEmailLog.DoesNotExist:
                print(f"⚠️ RSVPEmailLog with ID {log_id} not found")
        return {"status": "error", "message": "Participant not found."}
    except Exception as e:
        print(f"❌ Error in send_rsvp_email_task for participant {participant_id}: {e}")
        if log_id:
            try:
                email_log = RSVPEmailLog.objects.get(id=log_id)
                email_log.emails_failed += 1
                email_log.log_messages.append(
                    {
                        "type": "error",
                        "timestamp": timezone.now().isoformat(),
                        "message": f"Error in send_rsvp_email_task: {str(e)}",
                        "participant": f"ID: {participant_id}",
                        "email_type": "rsvp",
                        "error_details": str(e),
                    }
                )
                email_log.save()
            except RSVPEmailLog.DoesNotExist:
                print(f"⚠️ RSVPEmailLog with ID {log_id} not found")
        return {"status": "error", "message": f"Error sending RSVP email: {str(e)}"}


@shared_task
def send_bulk_rsvp_emails_task(event_id, participant_ids, user_id):
    """
    Celery task to send bulk RSVP emails to multiple participants.
    This replaces the threading approach in views.py.
    """
    try:
        from .models import Event, Participant, RSVPEmailLog
        from django.contrib.auth.models import User
        from django.utils import timezone

        event = Event.objects.get(id=event_id)
        user = User.objects.get(id=user_id)
        participants = Participant.objects.filter(id__in=participant_ids, event=event)

        # Create or get email log
        email_log, created = RSVPEmailLog.objects.get_or_create(
            event=event,
            user=user,
            status="in_progress",
            defaults={
                "total_recipients": participants.count(),
                "emails_sent": 0,
                "emails_failed": 0,
            },
        )

        if not created:
            # Update existing log
            email_log.status = "in_progress"
            email_log.total_recipients = participants.count()
            email_log.emails_sent = 0
            email_log.emails_failed = 0
            email_log.log_messages = []
            email_log.save()

        # Queue individual RSVP email tasks for each participant
        # Each task will update the log independently
        for participant in participants:
            try:
                # Send RSVP email using the existing task with log_id
                send_rsvp_email_task.delay(participant.id, email_log.id)
            except Exception as e:
                print(f"❌ Error queuing RSVP email for {participant.email}: {e}")
                # Update log for queuing errors
                email_log.emails_failed += 1
                email_log.save()

                # Schedule a task to check completion status after a delay
        check_bulk_rsvp_completion.apply_async(
            args=[email_log.id], countdown=60  # Check after 60 seconds
        )

        print(f"✅ Queued {participants.count()} RSVP email tasks")

        return {
            "status": "success",
            "message": f"Queued {participants.count()} RSVP email tasks",
            "log_id": email_log.id,
        }

        print(
            f"✅ Bulk RSVP email task completed: {emails_sent} sent, {emails_failed} failed"
        )

        return {
            "status": "success",
            "message": f"Bulk RSVP emails completed: {emails_sent} sent, {emails_failed} failed",
            "emails_sent": emails_sent,
            "emails_failed": emails_failed,
        }

    except Exception as e:
        print(f"❌ Error in bulk RSVP email task: {e}")

        # Update log as failed
        try:
            email_log.status = "failed"
            email_log.log_messages.append(
                {
                    "type": "error",
                    "timestamp": timezone.now().isoformat(),
                    "message": f"Bulk RSVP task failed: {str(e)}",
                    "email_type": "bulk_rsvp",
                    "error_details": str(e),
                }
            )
            email_log.completed_at = timezone.now()
            email_log.save()
        except:
            pass

        return {
            "status": "error",
            "message": f"Error in bulk RSVP email task: {str(e)}",
        }


@shared_task
def check_bulk_rsvp_completion(log_id):
    """
    Check if all RSVP emails in a bulk operation have been processed.
    This task is scheduled to run after the bulk operation starts.
    """
    from .models import RSVPEmailLog
    from django.utils import timezone

    try:
        email_log = RSVPEmailLog.objects.get(id=log_id)
        total_processed = email_log.emails_sent + email_log.emails_failed
        if total_processed >= email_log.total_recipients:
            # All emails have been processed
            email_log.status = "completed"
            email_log.completed_at = timezone.now()
            email_log.log_messages.append(
                {
                    "type": "success",
                    "timestamp": timezone.now().isoformat(),
                    "message": f"Bulk RSVP operation completed: {email_log.emails_sent} sent, {email_log.emails_failed} failed",
                    "email_type": "bulk_rsvp",
                    "total_recipients": email_log.total_recipients,
                    "successful_sends": email_log.emails_sent,
                    "failed_sends": email_log.emails_failed,
                }
            )
            email_log.save()
            print(
                f"✅ Bulk RSVP operation {log_id} completed: {email_log.emails_sent} sent, {email_log.emails_failed} failed"
            )
        else:
            # Not all emails processed yet, schedule another check
            check_bulk_rsvp_completion.apply_async(
                args=[log_id], countdown=30  # Check again in 30 seconds
            )
            print(
                f"⏳ Bulk RSVP operation {log_id}: {total_processed}/{email_log.total_recipients} processed, checking again..."
            )
    except RSVPEmailLog.DoesNotExist:
        print(f"❌ RSVPEmailLog with ID {log_id} not found")
    except Exception as e:
        print(f"❌ Error checking bulk RSVP completion for log {log_id}: {e}")


@shared_task
def process_registration_task(participant_id):
    """
    Celery task to process participant registration.
    This replaces the threading approach in signals.py.
    """
    try:
        from .models import Participant
        from .utils import generate_pdf_ticket

        participant = Participant.objects.get(id=participant_id)

        # Send registration email
        send_registration_email_task.delay(participant.id)

        # Handle auto approval
        if (
            participant.event.auto_approval_enabled
            and participant.approval_status == "pending"
        ):
            participant.approval_status = "approved"
            participant.save(update_fields=["approval_status"])

            # If auto approval AND tickets are enabled: generate tickets and send ticket email
            if participant.event.tickets:
                qr_path = participant.generate_qr_code()  # Generate QR code
                pdf_path = generate_pdf_ticket(participant, qr_path)  # Generate PDF

                if pdf_path:  # Only save if the PDF was generated successfully
                    participant.pdf_ticket = pdf_path
                    participant.save(update_fields=["pdf_ticket"])
                    # Send ticket email with PDF attachment
                    send_ticket_email_task.delay(participant.id)
                    print(
                        f"✅ Auto-approved with tickets: {participant.name} for {participant.event.event_name}"
                    )
                else:
                    print(f"❌ Failed to generate PDF ticket for {participant.name}")
            else:
                print(
                    f"✅ Auto-approved without tickets: {participant.name} for {participant.event.event_name}"
                )
        else:
            # Auto approval disabled: participant remains in "pending" status
            print(
                f"📋 Registration pending approval: {participant.name} for {participant.event.event_name}"
            )
            if participant.event.tickets:
                print(
                    f"🎫 Tickets will be generated upon manual approval: {participant.name}"
                )
            else:
                print(
                    f"📋 No tickets needed: {participant.name} for {participant.event.event_name}"
                )

        return {
            "status": "success",
            "message": f"Registration processing completed for {participant.name}",
        }

    except Participant.DoesNotExist:
        print(f"❌ Participant with ID {participant_id} not found")
        return {"status": "error", "message": "Participant not found."}
    except Exception as e:
        print(f"❌ Error processing registration for participant {participant_id}: {e}")
        return {
            "status": "error",
            "message": f"Error processing registration: {str(e)}",
        }


@shared_task
def process_approval_task(participant_id):
    """
    Celery task to process participant approval.
    This replaces the threading approach in signals.py.
    """
    try:
        from .models import Participant
        from .utils import generate_pdf_ticket

        participant = Participant.objects.get(id=participant_id)

        # Send approval email
        send_approval_email_task.delay(participant.id)

        # If tickets are enabled, generate tickets and send ticket email
        if participant.event.tickets:
            print(f"🎫 Tickets are enabled for {participant.event.event_name}")
            # Generate tickets if they don't exist yet (for manual approval cases)
            if not participant.pdf_ticket:
                qr_path = participant.generate_qr_code()  # Generate QR code
                pdf_path = generate_pdf_ticket(participant, qr_path)  # Generate PDF

                if pdf_path:
                    participant.pdf_ticket = pdf_path
                    participant.save(update_fields=["pdf_ticket"])
                    print(
                        f"🎫 Tickets generated for manual approval: {participant.name}"
                    )
                else:
                    print(f"❌ Failed to generate PDF ticket for {participant.name}")
                    return {
                        "status": "error",
                        "message": f"Failed to generate PDF ticket for {participant.name}",
                    }

            # Send ticket email
            send_ticket_email_task.delay(participant.id)
            print(f"🎫 Ticket email sent after manual approval: {participant.name}")
        else:
            print(f"✅ Participant approved without tickets: {participant.name}")

        return {
            "status": "success",
            "message": f"Approval processing completed for {participant.name}",
        }

    except Participant.DoesNotExist:
        print(f"❌ Participant with ID {participant_id} not found")
        return {"status": "error", "message": "Participant not found."}
    except Exception as e:
        print(f"❌ Error processing approval for participant {participant_id}: {e}")
        return {"status": "error", "message": f"Error processing approval: {str(e)}"}


@shared_task
def process_rejection_task(participant_id):
    """
    Celery task to process participant rejection.
    This replaces the threading approach in signals.py.
    """
    try:
        from .models import Participant

        participant = Participant.objects.get(id=participant_id)

        # Send rejection email
        send_rejection_email_task.delay(participant.id)
        print(f"❌ Participant rejected: {participant.name}")

        return {
            "status": "success",
            "message": f"Rejection processing completed for {participant.name}",
        }

    except Participant.DoesNotExist:
        print(f"❌ Participant with ID {participant_id} not found")
        return {"status": "error", "message": "Participant not found."}
    except Exception as e:
        print(f"❌ Error processing rejection for participant {participant_id}: {e}")
        return {"status": "error", "message": f"Error processing rejection: {str(e)}"}


@shared_task
def bulk_generate_certificates_task(event_id, user_id):
    """
    Celery task to generate certificates for all participants in an event.
    """
    try:
        from .models import Event, Participant, Attendance
        from django.contrib.auth.models import User
        from django.utils import timezone
        from .utils import generate_certificate_for_participant

        event = Event.objects.get(id=event_id)
        user = User.objects.get(id=user_id)

        # Create certificate generation log
        from .models import CertificateGenerationLog

        cert_log = CertificateGenerationLog.objects.create(
            event=event,
            user=user,
            status="in_progress",
            total_participants=0,
            processed_participants=0,
            successful_generations=0,
            failed_generations=0,
            log_messages=[],
        )

        # Get participants who have attended the event
        participants = Participant.objects.filter(
            event=event, attendance__event=event, attendance__present=True
        ).distinct()
        total_participants = participants.count()
        print("Participants:", participants)

        if not participants.exists():
            cert_log.status = "failed"
            cert_log.log_messages.append(
                {
                    "type": "error",
                    "timestamp": timezone.now().isoformat(),
                    "message": "No participants with attendance records found for this event",
                    "participant": None,
                }
            )
            cert_log.completed_at = timezone.now()
            cert_log.save()
            return {
                "status": "error",
                "message": "No participants with attendance records found for this event",
            }

        # Update total participants
        cert_log.total_participants = total_participants
        cert_log.save()

        print(
            f"🔄 Starting bulk certificate generation for {total_participants} participants with attendance..."
        )

        successful = 0
        failed = 0

        # Process each participant
        for participant in participants:
            try:
                cert_log.processed_participants += 1
                cert_log.save()

                print(f"Generating certificate for: {participant.name}")

                # Use the shared utility function
                success, message = generate_certificate_for_participant(
                    event, participant
                )

                if success:
                    successful += 1
                    cert_log.successful_generations += 1
                    cert_log.log_messages.append(
                        {
                            "type": "success",
                            "timestamp": timezone.now().isoformat(),
                            "message": f"Successfully generated certificate for {participant.name} ({participant.email})",
                            "participant": f"{participant.name} ({participant.email})",
                        }
                    )
                    print(f"✅ {message}")
                else:
                    failed += 1
                    cert_log.failed_generations += 1
                    cert_log.log_messages.append(
                        {
                            "type": "error",
                            "timestamp": timezone.now().isoformat(),
                            "message": f"Failed to generate certificate for {participant.name} ({participant.email}): {message}",
                            "participant": f"{participant.name} ({participant.email})",
                        }
                    )
                    print(f"❌ {message}")

                cert_log.save()

            except Exception as e:
                failed += 1
                cert_log.failed_generations += 1
                error_msg = (
                    f"Exception generating certificate for {participant.name}: {str(e)}"
                )
                cert_log.log_messages.append(
                    {
                        "type": "error",
                        "timestamp": timezone.now().isoformat(),
                        "message": error_msg,
                        "participant": f"{participant.name} ({participant.email})",
                    }
                )
                cert_log.save()
                print(f"❌ {error_msg}")

        # Mark as completed
        cert_log.status = "completed"
        cert_log.completed_at = timezone.now()
        cert_log.save()

        print(
            f"✅ Bulk certificate generation completed: {successful} successful, {failed} failed"
        )

        return {
            "status": "success",
            "message": f"Bulk certificate generation completed: {successful} successful, {failed} failed",
            "successful": successful,
            "failed": failed,
            "total": total_participants,
        }

    except Exception as e:
        print(f"❌ Error in bulk certificate generation task: {e}")
        return {"status": "error", "message": f"Task error: {str(e)}"}


@shared_task
def send_rsvp_reminders_for_upcoming_events():
    """
    Periodic task to send RSVP reminders for all 'on-going' events from tomorrow to 5 days ahead.
    For each event, finds participants without RSVPResponse and sends them RSVP emails using the existing bulk task.
    """
    from .models import Event, Participant, RSVPResponse
    from django.contrib.auth.models import User
    from django.utils import timezone

    tomorrow = date.today() + timedelta(days=1)
    five_days = date.today() + timedelta(days=5)

    # Find all 'on-going' events in the date range (from tomorrow to 5 days ahead)
    events = Event.objects.filter(
        event_date__gte=tomorrow,
        event_date__lte=five_days,
        status__name__iexact="on-going",
    )

    for event in events:
        # Get all participants for the event
        participants = Participant.objects.filter(event=event)
        # Get IDs of participants who have RSVPResponse for this event
        responded_ids = set(
            RSVPResponse.objects.filter(event=event).values_list(
                "participant_id", flat=True
            )
        )
        # Filter participants who have NOT responded
        no_rsvp_participants = [p for p in participants if p.id not in responded_ids]
        if no_rsvp_participants:
            user = (
                User.objects.filter(is_superuser=True).first() or User.objects.first()
            )
            participant_ids = [p.id for p in no_rsvp_participants]
            send_bulk_rsvp_emails_task.delay(event.id, participant_ids, user.id)
            print(
                f"[RSVP REMINDER] Queued reminders for event '{event.event_name}' to {len(participant_ids)} participants."
            )


@shared_task
def bulk_send_certificates_task(event_id, user_id):
    """
    Celery task to send certificates to all participants who have certificates generated.
    """
    try:
        from .models import Event, Participant, EventEmail, RSVPEmailLog
        from django.contrib.auth.models import User
        from django.utils import timezone
        from django.core.mail import EmailMessage, get_connection
        from django.template import Template, Context

        event = Event.objects.get(id=event_id)
        user = User.objects.get(id=user_id)

        # Get company email configuration
        email_config = getattr(event.company, "email_config", None)
        if not email_config:
            return {
                "status": "error",
                "message": f"No email configuration found for company {event.company.name}",
            }

        # Create SMTP connection
        connection = get_connection(
            host=email_config.smtp_server,
            port=email_config.smtp_port,
            username=email_config.email_address,
            password=email_config.email_password,
            use_tls=email_config.use_tls,
            use_ssl=email_config.use_ssl,
        )

        # Get all participants who have certificates
        participants = Participant.objects.filter(
            event=event, certificate__isnull=False
        )

        # Create email log
        email_log = RSVPEmailLog.objects.create(
            event=event,
            user=user,
            status="in_progress",
            total_recipients=participants.count(),
            emails_sent=0,
            emails_failed=0,
        )

        # Get the email template
        email_template = EventEmail.objects.get(event=event, reason="certificates")

        successful_count = 0
        failed_count = 0
        error_messages = []

        for participant in participants:
            try:
                # Prepare email context
                context = {
                    "name": participant.name,
                    "participant_name": participant.name,
                    "event_name": event.event_name,
                    "event_date": event.event_date,
                    "event_location": event.location,
                    "company_name": event.company.name if event.company else "",
                    "certificate_url": participant.certificate.url,
                }

                # Render email subject and body
                subject = Template(email_template.subject).render(Context(context))
                body = Template(email_template.body).render(Context(context))

                # Create and send email
                email = EmailMessage(
                    subject=subject,
                    body=body,
                    from_email=email_config.email_address,  # Use company email
                    to=[participant.email],
                    connection=connection,  # Use company SMTP connection
                )

                # Set HTML content type
                email.content_subtype = "html"  # Support HTML in email templates

                # Attach the certificate
                if participant.certificate:
                    email.attach_file(participant.certificate.path)

                email.send()
                successful_count += 1
                email_log.emails_sent += 1
                email_log.save()

            except Exception as e:
                failed_count += 1
                email_log.emails_failed += 1
                error_messages.append(f"Error sending to {participant.email}: {str(e)}")
                email_log.save()

        # Update log with final status
        completion_message = f"Certificate sending completed. Successfully sent: {successful_count}, Failed: {failed_count}"
        if error_messages:
            completion_message = (
                completion_message + "\n\nErrors:\n" + "\n".join(error_messages)
            )

        email_log.status = "completed"
        email_log.log_messages.append(
            {
                "type": "success",
                "timestamp": timezone.now().isoformat(),
                "message": completion_message,
                "email_type": "certificate_sending",
                "total_recipients": participants.count(),
                "successful_sends": successful_count,
                "failed_sends": failed_count,
                "errors": error_messages if error_messages else [],
            }
        )
        email_log.completed_at = timezone.now()
        email_log.save()

        return {
            "status": "success",
            "message": completion_message,
            "successful_count": successful_count,
            "failed_count": failed_count,
        }

    except Exception as e:
        if "email_log" in locals():
            email_log.status = "failed"
            email_log.log_messages.append(
                {
                    "type": "error",
                    "timestamp": timezone.now().isoformat(),
                    "message": f"Certificate sending task failed: {str(e)}",
                    "email_type": "certificate_sending",
                    "error_details": str(e),
                }
            )
            email_log.completed_at = timezone.now()
            email_log.save()

        return {"status": "error", "message": str(e)}
