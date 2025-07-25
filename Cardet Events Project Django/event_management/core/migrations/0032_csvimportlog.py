# Generated by Django 5.1.6 on 2025-07-02 11:15

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0031_add_pdf_validation'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CSVImportLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('in_progress', 'In Progress'), ('completed', 'Completed'), ('failed', 'Failed')], default='in_progress', max_length=20)),
                ('total_rows', models.PositiveIntegerField(default=0)),
                ('processed_rows', models.PositiveIntegerField(default=0)),
                ('successful_imports', models.PositiveIntegerField(default=0)),
                ('failed_imports', models.PositiveIntegerField(default=0)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('error_messages', models.JSONField(blank=True, default=list)),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='csv_import_logs', to='core.event')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-started_at'],
            },
        ),
    ]
