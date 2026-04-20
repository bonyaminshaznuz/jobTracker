import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update a superuser from environment variables"

    def add_arguments(self, parser):
        parser.add_argument("--username", default=os.getenv("DJANGO_SUPERUSER_USERNAME", ""))
        parser.add_argument("--email", default=os.getenv("DJANGO_SUPERUSER_EMAIL", ""))
        parser.add_argument("--password", default=os.getenv("DJANGO_SUPERUSER_PASSWORD", ""))

    def handle(self, *args, **options):
        username = (options["username"] or "").strip()
        email = (options["email"] or "").strip()
        password = options["password"] or ""

        if not username:
            self.stdout.write(self.style.WARNING("Skipping superuser creation: DJANGO_SUPERUSER_USERNAME is not set."))
            return

        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )

        changed = created
        if email and user.email != email:
            user.email = email
            changed = True

        if not user.is_staff:
            user.is_staff = True
            changed = True

        if not user.is_superuser:
            user.is_superuser = True
            changed = True

        if password:
            user.set_password(password)
            changed = True

        if changed:
            user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"Superuser created: {username}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Superuser ensured: {username}"))