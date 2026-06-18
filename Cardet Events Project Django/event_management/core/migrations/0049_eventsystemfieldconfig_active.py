from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0048_eventsystemfieldconfig_remove_participant_phone"),
    ]

    operations = [
        migrations.AddField(
            model_name="eventsystemfieldconfig",
            name="active",
            field=models.BooleanField(default=True),
        ),
    ]
