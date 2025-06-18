from django import forms
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
        fields = ["label", "field_type", "required", "options", "is_email_identifier"]
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
                    "placeholder": "Enter comma-separated options for select field type",
                }
            ),
            "is_email_identifier": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop("event", None)
        super().__init__(*args, **kwargs)

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
