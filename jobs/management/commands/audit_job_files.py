from django.core.management.base import BaseCommand

from jobs.models import JobApplication


class Command(BaseCommand):
    help = "Audit JobApplication file references and optionally clear missing file paths."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear-missing",
            action="store_true",
            help="Clear cv_file/cover_letter_file DB values when file is missing in storage.",
        )

    def handle(self, *args, **options):
        clear_missing = options["clear_missing"]

        total_jobs = 0
        cv_missing = 0
        cover_missing = 0
        updated_jobs = 0

        queryset = JobApplication.objects.all().only("id", "cv_file", "cover_letter_file")

        for job in queryset.iterator():
            total_jobs += 1
            update_fields = []

            if job.cv_file and job.cv_file.name:
                cv_exists = False
                try:
                    cv_exists = job.cv_file.storage.exists(job.cv_file.name)
                except Exception:
                    cv_exists = False

                if not cv_exists:
                    cv_missing += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Job #{job.id}: missing CV storage file -> {job.cv_file.name}"
                        )
                    )
                    if clear_missing:
                        job.cv_file = None
                        update_fields.append("cv_file")

            if job.cover_letter_file and job.cover_letter_file.name:
                cover_exists = False
                try:
                    cover_exists = job.cover_letter_file.storage.exists(job.cover_letter_file.name)
                except Exception:
                    cover_exists = False

                if not cover_exists:
                    cover_missing += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Job #{job.id}: missing cover letter storage file -> {job.cover_letter_file.name}"
                        )
                    )
                    if clear_missing:
                        job.cover_letter_file = None
                        update_fields.append("cover_letter_file")

            if update_fields:
                update_fields.append("updated_at")
                job.save(update_fields=update_fields)
                updated_jobs += 1

        self.stdout.write("")
        self.stdout.write(f"Jobs scanned: {total_jobs}")
        self.stdout.write(f"Missing CV files: {cv_missing}")
        self.stdout.write(f"Missing cover letter files: {cover_missing}")
        if clear_missing:
            self.stdout.write(self.style.SUCCESS(f"Rows updated: {updated_jobs}"))
        else:
            self.stdout.write("No DB updates applied. Use --clear-missing to repair broken references.")
