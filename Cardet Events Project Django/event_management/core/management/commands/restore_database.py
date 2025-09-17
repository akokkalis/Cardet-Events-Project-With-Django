import os
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.conf import settings


class Command(BaseCommand):
    help = "Restore data from a JSON dump (e.g., from SQLite) into PostgreSQL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default="backup.json",
            help="Filename of the backup JSON to restore from (default: backup.json)",
        )

    def handle(self, *args, **options):
        file_name = options["file"]
        backup_path = os.path.join(settings.BASE_DIR, "backups", file_name)

        if not os.path.exists(backup_path):
            raise CommandError(f"Backup file '{backup_path}' does not exist.")

        self.stdout.write(f"📦 Restoring data from {backup_path}...")

        try:
            call_command("loaddata", backup_path)
            self.stdout.write(self.style.SUCCESS("✅ Database restored successfully."))
        except Exception as e:
            raise CommandError(f"❌ Restore failed: {str(e)}")
