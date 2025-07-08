from django import forms
from django.db import models
from .models import (
    Event,
    Company,
    Status,
    Participant,
    EventCustomField,
    EventEmail,
    EmailConfiguration,
)
from ckeditor.widgets import CKEditorWidget


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ["name", "email", "phone", "address", "logo"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Enter company name",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Enter company email",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Enter phone number (optional)",
                }
            ),
            "address": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "rows": "3",
                    "placeholder": "Enter company address (optional)",
                }
            ),
            "logo": forms.ClearableFileInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "accept": "image/*",
                }
            ),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email:
            # Check if email already exists for another company
            existing_company = Company.objects.filter(email=email).exclude(
                pk=self.instance.pk if self.instance else None
            )
            if existing_company.exists():
                raise forms.ValidationError(
                    "A company with this email address already exists."
                )
        return email

    def clean_name(self):
        name = self.cleaned_data.get("name")
        if name:
            # Check if company name already exists (case-insensitive)
            existing_company = Company.objects.filter(name__iexact=name).exclude(
                pk=self.instance.pk if self.instance else None
            )
            if existing_company.exists():
                raise forms.ValidationError("A company with this name already exists.")
        return name


class EventForm(forms.ModelForm):

    class Meta:
        model = Event
        fields = [
            "company",
            "event_name",
            "event_date",
            "start_time",
            "end_time",
            "location",
            "description",
            "tickets",
            "has_registration_limit",
            "registration_limit",
            "signatures",
            "public_registration_enabled",
            "auto_approval_enabled",
            "image",
            "certificate",
            "status",
        ]
        widgets = {
            "company": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                }
            ),
            "event_name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Enter event name",
                }
            ),
            "event_date": forms.DateInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "type": "date",
                }
            ),
            "start_time": forms.TimeInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "type": "time",
                }
            ),
            "end_time": forms.TimeInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "type": "time",
                }
            ),
            "location": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Enter event location",
                }
            ),
            "description": CKEditorWidget(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                }
            ),
            "tickets": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded",
                    "title": "Enable this if you want to have ticketing system for the event.",
                }
            ),
            "has_registration_limit": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded",
                    "title": "Enable this if you want to limit the number of registrations for this event.",
                }
            ),
            "registration_limit": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "min": "1",
                    "title": "Maximum number of participants allowed to register (only applies if registration limit is enabled).",
                }
            ),
            "signatures": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded",
                    "title": "Enable this if you want to collect signatures from participants at the event.",
                }
            ),
            "public_registration_enabled": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded",
                    "title": "Enable this if you want to allow public registration via link.",
                }
            ),
            "auto_approval_enabled": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded",
                    "title": "Enable this if you want registrations to be automatically approved. If disabled, registrations will require manual approval.",
                }
            ),
            "image": forms.ClearableFileInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "accept": "image/*",
                }
            ),
            "certificate": forms.ClearableFileInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "accept": ".pdf",
                    "title": "Upload a PDF certificate template file for this event. Use placeholders like {{participant_name}}, {{event_name}}, {{event_date}}, {{company_name}} for personalization.",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["company"].queryset = Company.objects.all()
        self.fields["status"].queryset = (
            Status.objects.all()
        )  # Allow selection from all companies


class ParticipantForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop("event", None)
        super().__init__(*args, **kwargs)

        if self.event:
            custom_fields = EventCustomField.objects.filter(event=self.event).order_by(
                "order"
            )
            for field_model in custom_fields:
                field_name = f"custom_field_{field_model.id}"
                field_kwargs = {
                    "label": field_model.label,
                    "required": field_model.required,
                    "help_text": field_model.help_text,
                }

                if field_model.field_type == "text":
                    self.fields[field_name] = forms.CharField(**field_kwargs)
                elif field_model.field_type == "textarea":
                    self.fields[field_name] = forms.CharField(
                        widget=forms.Textarea, **field_kwargs
                    )
                elif field_model.field_type == "number":
                    self.fields[field_name] = forms.IntegerField(**field_kwargs)
                elif field_model.field_type == "email":
                    self.fields[field_name] = forms.EmailField(**field_kwargs)
                elif field_model.field_type == "checkbox":
                    self.fields[field_name] = forms.BooleanField(**field_kwargs)
                elif field_model.field_type == "date":
                    self.fields[field_name] = forms.DateField(
                        widget=forms.DateInput(attrs={"type": "date"}), **field_kwargs
                    )
                elif field_model.field_type == "time":
                    self.fields[field_name] = forms.TimeField(
                        widget=forms.TimeInput(attrs={"type": "time"}), **field_kwargs
                    )
                elif field_model.field_type == "datetime":
                    self.fields[field_name] = forms.DateTimeField(
                        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
                        **field_kwargs,
                    )
                elif field_model.field_type in ["select", "multiselect"]:
                    choices = [(option, option) for option in field_model.options_list]
                    if field_model.field_type == "select":
                        self.fields[field_name] = forms.ChoiceField(
                            choices=choices, **field_kwargs
                        )
                    else:
                        self.fields[field_name] = forms.MultipleChoiceField(
                            choices=choices,
                            widget=forms.CheckboxSelectMultiple,
                            **field_kwargs,
                        )
                elif field_model.field_type == "range":
                    min_val, max_val = field_model.range_values
                    self.fields[field_name] = forms.IntegerField(
                        min_value=min_val,
                        max_value=max_val,
                        widget=forms.NumberInput(
                            attrs={"type": "range", "min": min_val, "max": max_val}
                        ),
                        **field_kwargs,
                    )
                elif field_model.field_type == "file":
                    self.fields[field_name] = forms.FileField(**field_kwargs)

    class Meta:
        model = Participant
        fields = ["name", "email", "phone"]


class EventCustomFieldForm(forms.ModelForm):
    # Define system field names that cannot be used for custom fields
    SYSTEM_FIELD_NAMES = ["name", "email", "phone"]

    class Meta:
        model = EventCustomField
        fields = ["label", "field_type", "required", "options", "help_text", "order"]
        widgets = {
            "label": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                }
            ),
            "field_type": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                }
            ),
            "required": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                }
            ),
            "options": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "rows": "3",
                    "placeholder": "Enter comma-separated options (for select/multiselect) or min,max values (for range). Leave empty for text, number, email, checkbox, date, time, datetime, and file fields.",
                }
            ),
            "help_text": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Optional help text to guide users (e.g., 'Please enter your full legal name')",
                }
            ),
            "order": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "min": "1",
                    "placeholder": "Display order (1 = first, 2 = second, etc.)",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop("event", None)
        super().__init__(*args, **kwargs)

        # Auto-populate the next available order number for new fields
        if (
            self.event and not self.instance.pk
        ):  # Only for new fields (not editing existing ones)
            # Get the highest order number for this event and add 1
            max_order = EventCustomField.objects.filter(event=self.event).aggregate(
                max_order=models.Max("order")
            )["max_order"]
            next_order = (max_order or 0) + 1
            self.fields["order"].initial = next_order

    def clean_label(self):
        label = self.cleaned_data.get("label")
        if label:
            # Check if the label matches any system field names (case-insensitive)
            if label.lower() in [field.lower() for field in self.SYSTEM_FIELD_NAMES]:
                raise forms.ValidationError(
                    f"'{label}' is a system field name and cannot be used for custom fields. "
                    f"System fields are: {', '.join(self.SYSTEM_FIELD_NAMES)}"
                )

            # Check if a custom field with this label already exists for this event
            if self.event:
                existing_field = EventCustomField.objects.filter(
                    event=self.event, label__iexact=label
                ).exclude(pk=self.instance.pk if self.instance else None)

                if existing_field.exists():
                    raise forms.ValidationError(
                        f"A custom field with the label '{label}' already exists for this event."
                    )
        return label

    def clean(self):
        cleaned_data = super().clean()
        field_type = cleaned_data.get("field_type")
        options = cleaned_data.get("options")

        # Validate that options are provided for select and multiselect fields
        if field_type in ["select", "multiselect"] and not options:
            raise forms.ValidationError(
                f"Options are required for {field_type} field type. Please provide comma-separated options."
            )

        # Validate range field options (min,max format)
        if field_type == "range":
            if not options:
                raise forms.ValidationError(
                    "Range values are required for range field type. Please provide min and max values separated by comma (e.g., 0,100)."
                )
            try:
                range_parts = [part.strip() for part in options.split(",")]
                if len(range_parts) != 2:
                    raise forms.ValidationError(
                        "Range field requires exactly 2 values: min and max separated by comma (e.g., 0,100)."
                    )
                min_val, max_val = int(range_parts[0]), int(range_parts[1])
                if min_val >= max_val:
                    raise forms.ValidationError(
                        "Range minimum value must be less than maximum value."
                    )
            except ValueError:
                raise forms.ValidationError(
                    "Range values must be valid numbers separated by comma (e.g., 0,100)."
                )

        # Validate that options are not provided for fields that don't need them
        if (
            field_type
            in [
                "text",
                "textarea",
                "number",
                "email",
                "checkbox",
                "date",
                "time",
                "datetime",
                "file",
            ]
            and options
        ):
            raise forms.ValidationError(
                f"Options are not needed for {field_type} field type."
            )

        # Validate order uniqueness within the event
        order = cleaned_data.get("order")
        if self.event and order:
            existing_field = EventCustomField.objects.filter(
                event=self.event, order=order
            ).exclude(pk=self.instance.pk if self.instance else None)

            if existing_field.exists():
                existing_field_obj = existing_field.first()
                raise forms.ValidationError(
                    {
                        "order": f'Order number {order} is already used by field "{existing_field_obj.label}". Please choose a different order number.'
                    }
                )

        return cleaned_data


class EventEmailForm(forms.ModelForm):
    class Meta:
        model = EventEmail
        fields = ["reason", "subject", "body"]
        widgets = {
            "reason": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                }
            ),
            "subject": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Enter email subject line",
                }
            ),
            "body": CKEditorWidget(attrs={"class": "django-ckeditor-widget"}),
        }

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop("event", None)
        self.initial_reason = kwargs.pop("initial_reason", None)
        super().__init__(*args, **kwargs)

        # If creating a new template and reason is provided, set it and disable the field
        if not self.instance.pk and self.initial_reason:
            self.fields["reason"].initial = self.initial_reason
            self.fields["reason"].widget.attrs["readonly"] = True

        # Add help text for placeholders
        self.fields["body"].help_text = (
            "Available placeholders: {{ name }}, {{ event_name }}, {{ event_date }}, "
            "{{ event_location }}, {{ start_time }}, {{ end_time }}, {{ email }}, {{ phone }}"
        )

    def clean(self):
        cleaned_data = super().clean()
        reason = cleaned_data.get("reason")

        if self.event and reason:
            # Check if a template with this reason already exists for this event
            existing_template = EventEmail.objects.filter(
                event=self.event, reason=reason
            ).exclude(pk=self.instance.pk if self.instance else None)

            if existing_template.exists():
                raise forms.ValidationError(
                    f'An email template for "{reason}" already exists for this event.'
                )

        return cleaned_data


class EmailConfigurationForm(forms.ModelForm):
    class Meta:
        model = EmailConfiguration
        fields = [
            "smtp_server",
            "smtp_port",
            "email_address",
            "email_password",
            "use_tls",
            "use_ssl",
        ]
        widgets = {
            "smtp_server": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "e.g., smtp.gmail.com",
                }
            ),
            "smtp_port": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "587",
                    "min": "1",
                    "max": "65535",
                }
            ),
            "email_address": forms.EmailInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "your-email@domain.com",
                }
            ),
            "email_password": forms.PasswordInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Your email password or app-specific password",
                }
            ),
            "use_tls": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                }
            ),
            "use_ssl": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add help text
        self.fields["smtp_server"].help_text = (
            "SMTP server address (e.g., smtp.gmail.com, smtp.outlook.com)"
        )
        self.fields["smtp_port"].help_text = (
            "SMTP port number (typically 587 for TLS or 465 for SSL)"
        )
        self.fields["email_address"].help_text = (
            "The email address used to send emails from this company"
        )
        self.fields["email_password"].help_text = (
            "Email password or app-specific password"
        )
        self.fields["use_tls"].help_text = (
            "Enable TLS encryption (recommended for port 587)"
        )
        self.fields["use_ssl"].help_text = (
            "Enable SSL encryption (recommended for port 465)"
        )

    def clean(self):
        cleaned_data = super().clean()
        use_tls = cleaned_data.get("use_tls")
        use_ssl = cleaned_data.get("use_ssl")
        smtp_port = cleaned_data.get("smtp_port")

        # Validate that TLS and SSL are not both enabled
        if use_tls and use_ssl:
            raise forms.ValidationError(
                "Cannot use both TLS and SSL. Please select only one."
            )

        # Suggest appropriate port based on encryption method
        if use_tls and smtp_port and smtp_port != 587:
            self.add_error(
                "smtp_port", "Port 587 is typically used with TLS encryption."
            )

        if use_ssl and smtp_port and smtp_port != 465:
            self.add_error(
                "smtp_port", "Port 465 is typically used with SSL encryption."
            )

        return cleaned_data
