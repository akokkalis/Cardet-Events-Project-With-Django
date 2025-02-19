from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .views import (
    login_view,
    logout_view,
    event_list,
    event_create,
    event_edit,
    event_delete,
    event_detail,
    scan_qr,
    mark_attendance,
    sign_signature,
    export_zip,
    filter_events,
    register_participant_api,
    send_ticket_email_view,
    export_participants_csv_view,
    export_participants_pdf_view,
    public_register,
    download_ics_file,
    event_custom_fields,
    delete_custom_field,
    update_field_order,
    register_participant_view,
    edit_participant_view,
    download_custom_field_file,
    company_list,
    company_create,
    company_edit,
    company_detail,
    help_view,
    event_email_templates,
    add_email_template,
    edit_email_template,
    delete_email_template,
    approve_participant,
    reject_participant,
    set_participant_pending,
    check_participant_status,
    rsvp_response,
    rsvp_response_with_notes,
    event_rsvp_summary,
    send_rsvp_email_participant_view,
    send_bulk_rsvp_emails,
    check_rsvp_email_status,
    company_email_settings,
    bulk_approve_participants,
    export_participant_template,
    import_participants_csv,
    check_import_progress,
    generate_participant_certificate,
    bulk_generate_certificates,
    check_certificate_generation_progress,
    bulk_send_certificates,
    dashboard,
    dashboard_pending_participants,
    reports,
    participant_detail,
    logs_view,
    log_details_ajax,

    event_attendance_dashboard,
    export_attendance_csv,


)

# Import ticket views
from .ticket_views import (
    event_tickets,
    select_tickets,
    checkout,
    payment_success,
    payment_cancel,
    stripe_webhook,
    manage_ticket_types,
    create_ticket_type,
    edit_ticket_type,
    delete_ticket_type,
)

urlpatterns = [
    path("", event_list, name="event_list"),
    path("dashboard/", dashboard, name="dashboard"),
    path(
        "dashboard/pending-participants/",
        dashboard_pending_participants,
        name="dashboard_pending_participants",
    ),
    path("companies/", company_list, name="company_list"),
    path("companies/create/", company_create, name="company_create"),
    path("companies/<int:company_id>/", company_detail, name="company_detail"),
    path("companies/<int:company_id>/edit/", company_edit, name="company_edit"),
    path(
        "companies/<int:company_id>/email-settings/",
        company_email_settings,
        name="company_email_settings",
    ),
    path("events/create/", event_create, name="event_create"),
    path("events/<int:event_id>/", event_detail, name="event_detail"),

    path(
        "events/<int:event_id>/attendance-dashboard/",
        event_attendance_dashboard,
        name="event_attendance_dashboard",
    ),
    path(
        "events/<int:event_id>/export-attendance-csv/",
        export_attendance_csv,
        name="export_attendance_csv",
    ),


    path("events/<int:event_id>/edit/", event_edit, name="event_edit"),
    path(
        "events/<int:event_id>/custom-fields/",
        event_custom_fields,
        name="event_custom_fields",
    ),
    path(
        "events/<int:event_id>/email-templates/",
        event_email_templates,
        name="event_email_templates",
    ),
    path(
        "events/<int:event_id>/email-templates/add/",
        add_email_template,
        name="add_email_template",
    ),
    path(
        "events/<int:event_id>/email-templates/<int:template_id>/edit/",
        edit_email_template,
        name="edit_email_template",
    ),
    path(
        "events/<int:event_id>/email-templates/<int:template_id>/delete/",
        delete_email_template,
        name="delete_email_template",
    ),
    path(
        "events/<int:event_id>/custom-fields/delete/<int:field_id>/",
        delete_custom_field,
        name="delete_custom_field",
    ),
    path(
        "events/<int:event_id>/update-field-order/",
        update_field_order,
        name="update_field_order",
    ),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path(
        "events/<int:event_id>/add_participant/",
        register_participant_api,
        name="add_participant",
    ),
    path(
        "events/<int:event_id>/export_participants_csv/",
        export_participants_csv_view,
        name="export_participants_csv",
    ),
    path(
        "events/<int:event_id>/export_participants_pdf/",
        export_participants_pdf_view,
        name="export_participants_pdf",
    ),
    path("scan_qr/<int:event_id>/", scan_qr, name="scan_qr"),
    path(
        "sign_signature/<int:event_id>/<int:participant_id>/",
        sign_signature,
        name="sign_signature",
    ),
    path(
        "save_signature/<int:event_id>/<int:participant_id>/",
        sign_signature,
        name="save_signature",
    ),
    path("events/<int:event_id>/export_zip/", export_zip, name="export_zip"),
    path("filter_events/", filter_events, name="filter_events"),
    path("events/<int:event_id>/delete/", event_delete, name="event_delete"),
    path("mark_attendance/", mark_attendance, name="mark_attendance"),
    path(
        "api/register_participant/",
        register_participant_api,
        name="register_participant_api",
    ),
    path("send-ticket-email/", send_ticket_email_view, name="send_ticket_email"),
    path(
        "events/<int:event_id>/send_ticket/<int:participant_id>/",
        send_ticket_email_view,
        name="send_ticket",
    ),
    path("register/<uuid:event_uuid>/", public_register, name="public_register"),
    path("download_ics/<uuid:event_uuid>/", download_ics_file, name="download_ics"),
    path(
        "events/<int:event_id>/register-participant/",
        register_participant_view,
        name="register_participant",
    ),
    path(
        "events/<int:event_id>/participants/<int:participant_id>/edit/",
        edit_participant_view,
        name="edit_participant",
    ),
    path(
        "download-custom-file/<int:file_id>/",
        download_custom_field_file,
        name="download_custom_field_file",
    ),
    path("help/", help_view, name="help"),
    # Participant approval/rejection URLs
    path(
        "events/<int:event_id>/participants/<int:participant_id>/approve/",
        approve_participant,
        name="approve_participant",
    ),
    path(
        "events/<int:event_id>/participants/<int:participant_id>/reject/",
        reject_participant,
        name="reject_participant",
    ),
    path(
        "events/<int:event_id>/participants/<int:participant_id>/pending/",
        set_participant_pending,
        name="set_participant_pending",
    ),
    # AJAX endpoint for checking participant status
    path(
        "events/<int:event_id>/participants/<int:participant_id>/status/",
        check_participant_status,
        name="check_participant_status",
    ),
    # RSVP URLs
    path(
        "rsvp/<uuid:event_uuid>/<int:participant_id>/<str:response>/",
        rsvp_response,
        name="rsvp_response",
    ),
    path(
        "rsvp-form/<uuid:event_uuid>/<int:participant_id>/<str:response>/",
        rsvp_response_with_notes,
        name="rsvp_response_with_notes",
    ),
    path(
        "events/<int:event_id>/rsvp-summary/",
        event_rsvp_summary,
        name="event_rsvp_summary",
    ),
    # Send RSVP to a single participant
    path(
        "events/<int:event_id>/send-rsvp/<int:participant_id>/",
        send_rsvp_email_participant_view,
        name="send_rsvp_email_participant",
    ),
    # Bulk RSVP email sending
    path(
        "events/<int:event_id>/send-bulk-rsvp/",
        send_bulk_rsvp_emails,
        name="send_bulk_rsvp_emails",
    ),
    path(
        "rsvp-email-status/<int:log_id>/",
        check_rsvp_email_status,
        name="check_rsvp_email_status",
    ),
    # Bulk participant approval
    path(
        "events/<int:event_id>/bulk-approve/",
        bulk_approve_participants,
        name="bulk_approve_participants",
    ),
    # Participant import/export
    path(
        "events/<int:event_id>/export-participant-template/",
        export_participant_template,
        name="export_participant_template",
    ),
    path(
        "events/<int:event_id>/import-participants/",
        import_participants_csv,
        name="import_participants_csv",
    ),
    path(
        "import-progress/<int:import_id>/",
        check_import_progress,
        name="check_import_progress",
    ),
    # Certificate generation
    path(
        "events/<int:event_id>/participants/<int:participant_id>/generate-certificate/",
        generate_participant_certificate,
        name="generate_participant_certificate",
    ),
    path(
        "events/<int:event_id>/bulk-generate-certificates/",
        bulk_generate_certificates,
        name="bulk_generate_certificates",
    ),
    path(
        "certificate-generation-status/<int:log_id>/",
        check_certificate_generation_progress,
        name="check_certificate_generation_progress",
    ),
    path(
        "events/<int:event_id>/bulk-send-certificates/",
        bulk_send_certificates,
        name="bulk_send_certificates",
    ),
    path("reports/", reports, name="reports"),
    path("logs/", logs_view, name="logs"),
    path(
        "logs/<str:log_type>/<int:log_id>/details/",
        log_details_ajax,
        name="log_details_ajax",
    ),
    path(
        "participant/<str:participant_email>/",
        participant_detail,
        name="participant_detail",
    ),
    # Ticket URLs
    path("events/<int:event_id>/tickets/", event_tickets, name="event_tickets"),
    path(
        "events/<int:event_id>/tickets/select/", select_tickets, name="select_tickets"
    ),
    path("events/<int:event_id>/tickets/checkout/", checkout, name="checkout"),
    path(
        "events/<int:event_id>/tickets/payment/success/",
        payment_success,
        name="payment_success",
    ),
    path(
        "events/<int:event_id>/tickets/payment/cancel/",
        payment_cancel,
        name="payment_cancel",
    ),
    path("stripe/webhook/", stripe_webhook, name="stripe_webhook"),
    # Ticket Management URLs (Admin)
    path(
        "events/<int:event_id>/manage-tickets/",
        manage_ticket_types,
        name="manage_ticket_types",
    ),
    path(
        "events/<int:event_id>/create-ticket-type/",
        create_ticket_type,
        name="create_ticket_type",
    ),
    path(
        "events/<int:event_id>/edit-ticket-type/<int:ticket_type_id>/",
        edit_ticket_type,
        name="edit_ticket_type",
    ),
    path(
        "events/<int:event_id>/delete-ticket-type/<int:ticket_type_id>/",
        delete_ticket_type,
        name="delete_ticket_type",
    ),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
