import django.db.models.deletion
from django.db import migrations, models


def create_system_configs_for_existing_events(apps, schema_editor):
    Event = apps.get_model("core", "Event")
    EventSystemFieldConfig = apps.get_model("core", "EventSystemFieldConfig")
    for event in Event.objects.all():
        for order, field_name in enumerate(["name", "email", "phone"], start=1):
            EventSystemFieldConfig.objects.get_or_create(
                event=event,
                field_name=field_name,
                defaults={"order": order},
            )


def migrate_phone_to_submitted_data(apps, schema_editor):
    Participant = apps.get_model("core", "Participant")
    for p in Participant.objects.exclude(phone__isnull=True).exclude(phone=""):
        data = p.submitted_data or {}
        if "Phone" not in data:
            data["Phone"] = p.phone
            p.submitted_data = data
            p.save(update_fields=["submitted_data"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0047_event_rsvp_cutoff_hours"),
    ]

    operations = [
        migrations.CreateModel(
            name="EventSystemFieldConfig",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "field_name",
                    models.CharField(
                        choices=[
                            ("name", "Name"),
                            ("email", "Email"),
                            ("phone", "Phone"),
                        ],
                        max_length=20,
                    ),
                ),
                ("order", models.PositiveIntegerField(default=1)),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="system_field_configs",
                        to="core.event",
                    ),
                ),
            ],
            options={
                "ordering": ["order"],
                "unique_together": {("event", "field_name")},
            },
        ),
        migrations.RunPython(
            create_system_configs_for_existing_events,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            migrate_phone_to_submitted_data,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="participant",
            name="phone",
        ),
    ]
