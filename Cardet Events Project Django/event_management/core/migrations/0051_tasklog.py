import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0050_merge_20260617_1252"),
    ]

    operations = [
        migrations.CreateModel(
            name="TaskLog",
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
                ("task_id", models.CharField(db_index=True, max_length=255, unique=True)),
                (
                    "task_type",
                    models.CharField(
                        choices=[
                            ("registration", "Registration"),
                            ("approval", "Approval"),
                            ("rejection", "Rejection"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("in_progress", "In Progress"),
                            ("success", "Success"),
                            ("failure", "Failure"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("message", models.TextField(blank=True, default="")),
                (
                    "event",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="task_logs",
                        to="core.event",
                    ),
                ),
                ("participant_name", models.CharField(blank=True, max_length=255)),
                ("participant_email", models.EmailField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
