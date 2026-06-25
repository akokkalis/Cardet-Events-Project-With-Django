import core.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0052_exportlog"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="registration_qr_code",
            field=models.ImageField(
                blank=True, null=True, upload_to=core.models.event_registration_qr_path
            ),
        ),
    ]
