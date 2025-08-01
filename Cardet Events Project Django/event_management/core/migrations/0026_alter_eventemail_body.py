# Generated by Django 5.1.6 on 2025-06-24 09:57

import ckeditor.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_eventemail'),
    ]

    operations = [
        migrations.AlterField(
            model_name='eventemail',
            name='body',
            field=ckeditor.fields.RichTextField(help_text='Use placeholders like {{ name }}, {{ event_name }}, {{ event_date }}. HTML formatting is supported.'),
        ),
    ]
