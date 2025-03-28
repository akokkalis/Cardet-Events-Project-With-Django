from django import forms
from .models import Event, Company, Status, Participant


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
