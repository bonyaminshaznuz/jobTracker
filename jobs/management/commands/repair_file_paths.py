"""
Management command: repair_file_paths
======================================
Scans every JobApplication row and fixes corrupted FileField paths stored in
the database.  The most common corruption is a duplicated directory prefix,
e.g.  ``cvs/cvs/Bony_CV.pdf`` instead of ``cvs/Bony_CV.pdf``.

This happens when the ``_normalize_file_field_name`` helper on ``JobApplication``
ran more than once on the same row, or when ``upload_to`` and the normalizer
both prepended the same prefix.

Usage
-----
    # Dry-run (shows what would be changed, writes nothing):
    python manage.py repair_file_paths

    # Actually apply the DB fixes:
    python manage.py repair_file_paths --fix

    # Also print rows that look fine (verbose):
    python manage.py repair_file_paths --fix --verbose
"""

import posixpath

from django.core.management.base import BaseCommand

from jobs.models import JobApplication


def _strip_double_prefix(name: str, prefix: str) -> tuple[str, bool]:
    """Return ``(cleaned_name, was_changed)``.

    Removes one level of duplication if *name* starts with ``prefix/prefix/``.
    For example::

        "cvs/cvs/Bony_CV.pdf", "cvs"  →  "cvs/Bony_CV.pdf", True
        "cvs/Bony_CV.pdf",      "cvs"  →  "cvs/Bony_CV.pdf", False
    """
    doubled = f"{prefix}/{prefix}/"
    if name.startswith(doubled):
        return prefix + "/" + name[len(doubled):], True
    return name, False


class Command(BaseCommand):
    help = (
        "Detect and repair duplicated upload-path prefixes in JobApplication "
        "FileField values (e.g. cvs/cvs/file.pdf → cvs/file.pdf). "
        "Run without --fix for a safe dry-run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            default=False,
            help="Actually write the corrected paths to the database (default: dry-run).",
        )

    def handle(self, *args, **options):
        fix = options["fix"]
        verbosity = options["verbosity"]

        if fix:
            self.stdout.write(self.style.WARNING("Running in FIX mode — DB will be updated."))
        else:
            self.stdout.write("Running in DRY-RUN mode — no changes will be written.")
            self.stdout.write("Use --fix to apply changes.")
        self.stdout.write("")

        total = 0
        needs_fix = 0
        fixed = 0

        qs = JobApplication.objects.all().only("id", "cv_file", "cover_letter_file")

        for job in qs.iterator():
            total += 1
            update_fields = []
            job_changed = False

            # ---- cv_file ----
            if job.cv_file and job.cv_file.name:
                cleaned, changed = _strip_double_prefix(job.cv_file.name, "cvs")
                if changed:
                    needs_fix += 1
                    job_changed = True
                    self.stdout.write(
                        self.style.WARNING(
                            f"  Job #{job.id} cv_file:           {job.cv_file.name!r}"
                            f"  →  {cleaned!r}"
                        )
                    )
                    if fix:
                        job.cv_file.name = cleaned
                        update_fields.append("cv_file")
                elif verbosity >= 2:
                    self.stdout.write(f"  Job #{job.id} cv_file OK:       {job.cv_file.name!r}")

            # ---- cover_letter_file ----
            if job.cover_letter_file and job.cover_letter_file.name:
                cleaned, changed = _strip_double_prefix(
                    job.cover_letter_file.name, "cover_letters"
                )
                if changed:
                    needs_fix += 1
                    job_changed = True
                    self.stdout.write(
                        self.style.WARNING(
                            f"  Job #{job.id} cover_letter_file: {job.cover_letter_file.name!r}"
                            f"  →  {cleaned!r}"
                        )
                    )
                    if fix:
                        job.cover_letter_file.name = cleaned
                        update_fields.append("cover_letter_file")
                elif verbosity >= 2:
                    self.stdout.write(
                        f"  Job #{job.id} cover_letter_file OK: {job.cover_letter_file.name!r}"
                    )

            if fix and update_fields:
                update_fields.append("updated_at")
                # Use update() to bypass model.save() signals/normalizers.
                JobApplication.objects.filter(pk=job.pk).update(
                    **{f: getattr(job, f) for f in update_fields if f != "updated_at"},
                )
                fixed += 1

        self.stdout.write("")
        self.stdout.write(f"Jobs scanned:          {total}")
        self.stdout.write(f"Corrupted paths found: {needs_fix}")
        if fix:
            self.stdout.write(self.style.SUCCESS(f"Rows repaired:         {fixed}"))
        else:
            if needs_fix:
                self.stdout.write(
                    self.style.ERROR(
                        f"  {needs_fix} path(s) need repair. Re-run with --fix to apply."
                    )
                )
            else:
                self.stdout.write(self.style.SUCCESS("All paths look correct. No action needed."))
