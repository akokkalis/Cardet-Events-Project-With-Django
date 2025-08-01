# Generated by Django 5.1.6 on 2025-06-20 11:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_remove_is_email_identifier'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventcustomfield',
            name='help_text',
            field=models.CharField(blank=True, help_text='Optional help text to guide users when filling out this field', max_length=500, null=True),
        ),
        migrations.AlterField(
            model_name='eventcustomfield',
            name='field_type',
            field=models.CharField(choices=[('text', 'Text'), ('textarea', 'Textarea'), ('number', 'Number'), ('email', 'Email'), ('select', 'Select'), ('range', 'Range'), ('checkbox', 'True or False'), ('multiselect', 'Multi-select'), ('date', 'Date'), ('time', 'Time'), ('datetime', 'Date & Time')], max_length=20),
        ),
    ]
