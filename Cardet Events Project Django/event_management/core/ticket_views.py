import stripe
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import transaction
from django.urls import reverse
from decimal import Decimal
import json
import logging

from .models import Event, TicketType, Order, OrderItem, Payment, Participant
from .forms import TicketSelectionForm, ParticipantOrderForm, TicketTypeForm

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY
stripe.api_version = settings.STRIPE_API_VERSION

logger = logging.getLogger(__name__)


def event_tickets(request, event_id):
    """Display available tickets for an event and handle ticket selection"""
    event = get_object_or_404(Event, id=event_id)

    # Check if event has tickets enabled
    if not event.tickets:
        messages.error(request, "This event does not have ticketing enabled.")
        return redirect("event_detail", event_id=event_id)

    # Get available ticket types
    ticket_types = TicketType.objects.filter(event=event, is_active=True).order_by(
        "price"
    )

    # Check if any tickets are available
    if not ticket_types.exists():
        messages.info(request, "No tickets are currently available for this event.")
        return redirect("event_detail", event_id=event_id)

    if request.method == "POST":
        form = TicketSelectionForm(request.POST, event=event)
        if form.is_valid():
            # Store ticket selections in session
            ticket_selections = {}
            total_amount = Decimal("0.00")

            for field_name, quantity in form.cleaned_data.items():
                if field_name.startswith("ticket_") and quantity > 0:
                    ticket_id = int(field_name.split("_")[1])
                    ticket_type = get_object_or_404(TicketType, id=ticket_id)

                    # Verify ticket availability
                    if quantity > ticket_type.tickets_available:
                        messages.error(
                            request,
                            f"Only {ticket_type.tickets_available} tickets available for {ticket_type.name}",
                        )
                        return redirect("event_tickets", event_id=event_id)

                    ticket_selections[ticket_id] = {
                        "quantity": quantity,
                        "price": float(ticket_type.price),
                        "name": ticket_type.name,
                    }
                    total_amount += ticket_type.price * quantity

            # Store in session
            request.session["ticket_selections"] = ticket_selections
            request.session["total_amount"] = float(total_amount)

            return redirect("checkout", event_id=event_id)
    else:
        form = TicketSelectionForm(event=event)

    context = {
        "event": event,
        "ticket_types": ticket_types,
        "form": form,
    }
    return render(request, "tickets/event_tickets.html", context)


def select_tickets(request, event_id):
    """Handle ticket selection"""
    event = get_object_or_404(Event, id=event_id)

    if not event.tickets:
        messages.error(request, "This event does not have ticketing enabled.")
        return redirect("event_detail", event_id=event_id)

    # Get available ticket types
    ticket_types = TicketType.objects.filter(event=event, is_active=True).order_by(
        "price"
    )

    if request.method == "POST":
        form = TicketSelectionForm(request.POST, event=event)
        if form.is_valid():
            # Store ticket selections in session
            ticket_selections = {}
            total_amount = Decimal("0.00")

            for field_name, quantity in form.cleaned_data.items():
                if field_name.startswith("ticket_") and quantity > 0:
                    ticket_id = int(field_name.split("_")[1])
                    ticket_type = get_object_or_404(TicketType, id=ticket_id)

                    # Verify ticket availability
                    if quantity > ticket_type.tickets_available:
                        messages.error(
                            request,
                            f"Only {ticket_type.tickets_available} tickets available for {ticket_type.name}",
                        )
                        return redirect("select_tickets", event_id=event_id)

                    ticket_selections[ticket_id] = {
                        "quantity": quantity,
                        "price": float(ticket_type.price),
                        "name": ticket_type.name,
                    }
                    total_amount += ticket_type.price * quantity

            # Store in session
            request.session["ticket_selections"] = ticket_selections
            request.session["total_amount"] = float(total_amount)

            return redirect("checkout", event_id=event_id)
    else:
        form = TicketSelectionForm(event=event)

    context = {
        "event": event,
        "ticket_types": ticket_types,
        "form": form,
    }
    return render(request, "tickets/select_tickets.html", context)


def checkout(request, event_id):
    """Handle checkout process"""
    event = get_object_or_404(Event, id=event_id)

    # Check if ticket selections exist in session
    ticket_selections = request.session.get("ticket_selections", {})
    if not ticket_selections:
        messages.error(request, "No tickets selected. Please select tickets first.")
        return redirect("select_tickets", event_id=event_id)

    total_amount = Decimal(str(request.session.get("total_amount", 0)))

    if request.method == "POST":
        form = ParticipantOrderForm(request.POST)
        form.event = event  # Set event for validation

        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create or get participant
                    participant, created = Participant.objects.get_or_create(
                        event=event,
                        email=form.cleaned_data["email"],
                        defaults={
                            "name": form.cleaned_data["name"],
                            "phone": form.cleaned_data.get("phone", ""),
                            "approval_status": (
                                "approved" if event.auto_approval_enabled else "pending"
                            ),
                        },
                    )

                    # Create order
                    order = Order.objects.create(
                        participant=participant,
                        event=event,
                        total_amount=total_amount,
                        payment_status="pending",
                    )

                    # Create order items
                    for ticket_id, selection in ticket_selections.items():
                        ticket_type = get_object_or_404(TicketType, id=ticket_id)
                        OrderItem.objects.create(
                            order=order,
                            ticket_type=ticket_type,
                            quantity=selection["quantity"],
                            price_per_ticket=ticket_type.price,
                        )

                    # Create Stripe payment intent
                    intent = stripe.PaymentIntent.create(
                        amount=int(total_amount * 100),  # Convert to cents
                        currency="usd",
                        metadata={
                            "order_id": order.id,
                            "event_id": event.id,
                            "participant_email": participant.email,
                        },
                    )

                    # Create payment record
                    payment = Payment.objects.create(
                        order=order,
                        stripe_payment_intent_id=intent.id,
                        amount_paid=total_amount,
                        payment_status="pending",
                    )

                    # Store order ID in session for payment completion
                    request.session["order_id"] = order.id

                    context = {
                        "event": event,
                        "order": order,
                        "payment_intent_client_secret": intent.client_secret,
                        "stripe_public_key": settings.STRIPE_PUBLIC_KEY,
                        "total_amount": total_amount,
                    }
                    return render(request, "tickets/payment.html", context)

            except Exception as e:
                logger.error(f"Error creating order: {str(e)}")
                messages.error(
                    request,
                    "An error occurred while processing your order. Please try again.",
                )
                return redirect("checkout", event_id=event_id)
    else:
        form = ParticipantOrderForm()

    # Prepare order summary
    order_summary = []
    for ticket_id, selection in ticket_selections.items():
        ticket_type = get_object_or_404(TicketType, id=ticket_id)
        order_summary.append(
            {
                "ticket_type": ticket_type,
                "quantity": selection["quantity"],
                "subtotal": ticket_type.price * selection["quantity"],
            }
        )

    context = {
        "event": event,
        "form": form,
        "order_summary": order_summary,
        "total_amount": total_amount,
    }
    return render(request, "tickets/checkout.html", context)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Handle Stripe webhook events"""
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.error("Invalid payload in Stripe webhook")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid signature in Stripe webhook")
        return HttpResponse(status=400)

    # Handle the event
    if event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        handle_payment_success(payment_intent)
    elif event["type"] == "payment_intent.payment_failed":
        payment_intent = event["data"]["object"]
        handle_payment_failure(payment_intent)

    return HttpResponse(status=200)


def handle_payment_success(payment_intent):
    """Handle successful payment"""
    try:
        payment = Payment.objects.get(stripe_payment_intent_id=payment_intent["id"])
        payment.payment_status = "completed"
        payment.stripe_charge_id = payment_intent.get("latest_charge")
        payment.save()

        # Update order status
        order = payment.order
        order.payment_status = "completed"
        order.save()

        logger.info(f"Payment completed for order {order.id}")

    except Payment.DoesNotExist:
        logger.error(f"Payment not found for payment intent {payment_intent['id']}")


def handle_payment_failure(payment_intent):
    """Handle failed payment"""
    try:
        payment = Payment.objects.get(stripe_payment_intent_id=payment_intent["id"])
        payment.payment_status = "failed"
        payment.failure_reason = payment_intent.get("last_payment_error", {}).get(
            "message", "Unknown error"
        )
        payment.save()

        # Update order status
        order = payment.order
        order.payment_status = "failed"
        order.save()

        logger.info(f"Payment failed for order {order.id}")

    except Payment.DoesNotExist:
        logger.error(f"Payment not found for payment intent {payment_intent['id']}")


def payment_success(request, event_id):
    """Handle successful payment completion"""
    event = get_object_or_404(Event, id=event_id)
    order_id = request.session.get("order_id")

    if not order_id:
        messages.error(request, "Order not found.")
        return redirect("event_tickets", event_id=event_id)

    order = get_object_or_404(Order, id=order_id)

    # Clear session data
    request.session.pop("ticket_selections", None)
    request.session.pop("total_amount", None)
    request.session.pop("order_id", None)

    context = {
        "event": event,
        "order": order,
    }
    return render(request, "tickets/payment_success.html", context)


def payment_cancel(request, event_id):
    """Handle payment cancellation"""
    event = get_object_or_404(Event, id=event_id)

    # Clear session data
    request.session.pop("ticket_selections", None)
    request.session.pop("total_amount", None)
    request.session.pop("order_id", None)

    messages.info(request, "Payment was cancelled. You can try again anytime.")
    return redirect("select_tickets", event_id=event_id)


# Admin views for managing ticket types


def manage_ticket_types(request, event_id):
    """Manage ticket types for an event"""
    event = get_object_or_404(Event, id=event_id)
    ticket_types = TicketType.objects.filter(event=event).order_by("price")

    # Calculate totals
    total_max_quantity = sum(ticket_type.max_quantity for ticket_type in ticket_types)
    total_sold = sum(ticket_type.tickets_sold for ticket_type in ticket_types)
    active_types = ticket_types.filter(is_active=True).count()

    context = {
        "event": event,
        "ticket_types": ticket_types,
        "total_max_quantity": total_max_quantity,
        "total_sold": total_sold,
        "active_types": active_types,
    }
    return render(request, "tickets/manage_ticket_types.html", context)


def create_ticket_type(request, event_id):
    """Create a new ticket type"""
    event = get_object_or_404(Event, id=event_id)

    if request.method == "POST":
        form = TicketTypeForm(request.POST)
        if form.is_valid():
            ticket_type = form.save(commit=False)
            ticket_type.event = event
            ticket_type.save()
            messages.success(
                request, f"Ticket type '{ticket_type.name}' created successfully."
            )
            return redirect("manage_ticket_types", event_id=event_id)
    else:
        form = TicketTypeForm()

    context = {
        "event": event,
        "form": form,
        "title": "Create Ticket Type",
    }
    return render(request, "tickets/ticket_type_form.html", context)


def edit_ticket_type(request, event_id, ticket_type_id):
    """Edit an existing ticket type"""
    event = get_object_or_404(Event, id=event_id)
    ticket_type = get_object_or_404(TicketType, id=ticket_type_id, event=event)

    if request.method == "POST":
        form = TicketTypeForm(request.POST, instance=ticket_type)
        if form.is_valid():
            form.save()
            messages.success(
                request, f"Ticket type '{ticket_type.name}' updated successfully."
            )
            return redirect("manage_ticket_types", event_id=event_id)
    else:
        form = TicketTypeForm(instance=ticket_type)

    context = {
        "event": event,
        "form": form,
        "ticket_type": ticket_type,
        "title": "Edit Ticket Type",
    }
    return render(request, "tickets/ticket_type_form.html", context)


def delete_ticket_type(request, event_id, ticket_type_id):
    """Delete a ticket type"""
    event = get_object_or_404(Event, id=event_id)
    ticket_type = get_object_or_404(TicketType, id=ticket_type_id, event=event)

    if request.method == "POST":
        ticket_name = ticket_type.name
        ticket_type.delete()
        messages.success(request, f"Ticket type '{ticket_name}' deleted successfully.")
        return redirect("manage_ticket_types", event_id=event_id)

    context = {
        "event": event,
        "ticket_type": ticket_type,
    }
    return render(request, "tickets/confirm_delete_ticket_type.html", context)
