from celery import shared_task
import time
import os
from django.core.mail import EmailMessage, get_connection
from django.utils.html import strip_tags
from django.template import Template, Context
from .models import Participant, EventEmail
from .utils import email_body, generate_rsvp_urls


@shared_task
def test_hello(name):
    print(f"Hello, {name}! Task is running.")

    for i in range(10):
        print(f"Hello, {name}! Task is running. {i}")

    return f"Task completed for {name}"


@shared_task
def send_ticket_email_task(participant_id):
    """
    Celery task to send ticket email to a participant.
    This replaces the threading approach in send_ticket_email_view.
    """
    try:
        # Get the participant
        participant = Participant.objects.get(id=participant_id)

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

        return {
            "status": "success",
            "message": f"Ticket sent successfully to {participant.email}!",
        }

    except Participant.DoesNotExist:
        print(f"❌ Participant with ID {participant_id} not found")
        return {"status": "error", "message": "Participant not found."}
    except Exception as e:
        print(f"❌ Error sending email to participant {participant_id}: {e}")
        return {"status": "error", "message": f"Error sending email: {str(e)}"}


@shared_task
def send_approval_email_task(participant_id):
    """
    Celery task to send approval email to a participant.
    This replaces the threading approach in signals.py.
    """
    try:
        participant = Participant.objects.get(id=participant_id)

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

        return {
            "status": "success",
            "message": f"Approval email sent successfully to {participant.email}!",
        }

    except Participant.DoesNotExist:
        print(f"❌ Participant with ID {participant_id} not found")
        return {"status": "error", "message": "Participant not found."}
    except Exception as e:
        print(f"❌ Error sending approval email to participant {participant_id}: {e}")
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
                    email_log.error_message = "No RSVP email template found."
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
                    email_log.error_message = (
                        "No email configuration found for this company."
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
                    email_log.error_message = str(e)
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
                email_log.error_message = "Participant not found."
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
                email_log.error_message = str(e)
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
            email_log.error_message = ""
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
            email_log.error_message = str(e)
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
        from .models import Event, Participant
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
            error_messages=[],
        )

        # Get all participants
        participants = Participant.objects.filter(event=event)
        total_participants = participants.count()

        if not participants.exists():
            cert_log.status = "failed"
            cert_log.error_messages.append("No participants found for this event")
            cert_log.completed_at = timezone.now()
            cert_log.save()
            return {
                "status": "error",
                "message": "No participants found for this event",
            }

        # Update total participants
        cert_log.total_participants = total_participants
        cert_log.save()

        print(
            f"🔄 Starting bulk certificate generation for {total_participants} participants..."
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
                    print(f"✅ {message}")
                else:
                    failed += 1
                    cert_log.failed_generations += 1
                    cert_log.error_messages.append(
                        f"Failed for {participant.name}: {message}"
                    )
                    print(f"❌ {message}")

            except Exception as e:
                failed += 1
                cert_log.failed_generations += 1
                error_msg = (
                    f"Exception generating certificate for {participant.name}: {str(e)}"
                )
                cert_log.error_messages.append(error_msg)
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
