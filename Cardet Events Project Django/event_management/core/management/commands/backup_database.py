import os
import subprocess
import datetime
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Create a timestamped backup of the database."

    def handle(self, *args, **options):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(settings.BASE_DIR, "backups")
        os.makedirs(backup_dir, exist_ok=True)

        db_engine = settings.DATABASES["default"]["ENGINE"]

        if "sqlite3" in db_engine:
            db_name = settings.DATABASES["default"]["NAME"]
            backup_file = os.path.join(backup_dir, f"sqlite_backup_{timestamp}.db")
            self.stdout.write(f"Backing up SQLite database to {backup_file}")
            try:
                subprocess.run(["cp", db_name, backup_file], check=True)
                self.stdout.write(
                    self.style.SUCCESS("SQLite backup completed successfully.")
                )
            except subprocess.CalledProcessError as e:
                self.stderr.write(self.style.ERROR(f"Backup failed: {e}"))

        elif "postgresql" in db_engine:
            db = settings.DATABASES["default"]
            backup_file = os.path.join(backup_dir, f"pg_backup_{timestamp}.sql")
            command = [
                "pg_dump",
                "-U",
                db["USER"],
                "-h",
                db.get("HOST", "localhost"),
                "-p",
                str(db.get("PORT", 5432)),
                "-F",
                "c",
                "-f",
                backup_file,
                db["NAME"],
            ]
            self.stdout.write(f"Backing up PostgreSQL database to {backup_file}")
            try:
                env = os.environ.copy()
                env["PGPASSWORD"] = db["PASSWORD"]
                subprocess.run(command, check=True, env=env)
                self.stdout.write(
                    self.style.SUCCESS("PostgreSQL backup completed successfully.")
                )
            except subprocess.CalledProcessError as e:
                self.stderr.write(self.style.ERROR(f"Backup failed: {e}"))

        elif "mysql" in db_engine:
            db = settings.DATABASES["default"]
            backup_file = os.path.join(backup_dir, f"mysql_backup_{timestamp}.sql")
            command = [
                "mysqldump",
                "-u",
                db["USER"],
                f"-p{db['PASSWORD']}",
                "-h",
                db.get("HOST", "localhost"),
                "-P",
                str(db.get("PORT", 3306)),
                db["NAME"],
            ]
            self.stdout.write(f"Backing up MySQL database to {backup_file}")
            try:
                with open(backup_file, "w") as f:
                    subprocess.run(command, stdout=f, check=True)
                self.stdout.write(
                    self.style.SUCCESS("MySQL backup completed successfully.")
                )
            except subprocess.CalledProcessError as e:
                self.stderr.write(self.style.ERROR(f"Backup failed: {e}"))

        else:
            self.stderr.write(
                self.style.ERROR(f"Unsupported database engine: {db_engine}")
            )
