from django import forms
from django.db import models
from .models import Event, Company, Status, Participant, EventCustomField


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
            "image",
            "tickets",
            "signatures",
            "status",
            "public_registration_enabled",
        ]
        widgets = {
            "company": forms.Select(attrs={"class": "form-select"}),
            "event_date": forms.DateInput(
                attrs={"type": "date", "class": "form-input"}
            ),
            "start_time": forms.TimeInput(
                attrs={"type": "time", "class": "form-input"}
            ),
            "end_time": forms.TimeInput(attrs={"type": "time", "class": "form-input"}),
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["company"].queryset = Company.objects.all()
        self.fields["status"].queryset = (
            Status.objects.all()
        )  # Allow selection from all companies


class ParticipantForm(forms.ModelForm):
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
                    "placeholder": "Enter comma-separated options (for select/multiselect) or min,max values (for range)",
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
