from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from interviews.models import InterviewQuestion, InterviewRound
from jobs.models import Category, JobApplication, Reminder, log_activity


class Command(BaseCommand):
    help = "Seed sample job tracking data"

    def add_arguments(self, parser):
        parser.add_argument("--username", default="demo")
        parser.add_argument("--password", default="demo12345")

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]

        user, created = User.objects.get_or_create(username=username, defaults={"email": f"{username}@example.com"})
        if created:
            user.set_password(password)
            user.save()

        uncategorized, _ = Category.objects.get_or_create(user=user, name="Uncategorized")
        it_category, _ = Category.objects.get_or_create(user=user, name="IT")

        job, _ = JobApplication.objects.get_or_create(
            user=user,
            company_name="Acme Corp",
            job_title="Backend Django Engineer",
            defaults={
                "job_post_url": "https://example.com/jobs/backend",
                "location": JobApplication.LOCATION_REMOTE,
                "salary": 80000,
                "job_description": "Build scalable Django systems.",
                "date_applied": timezone.localdate() - timedelta(days=4),
                "status": JobApplication.STATUS_INTERVIEW,
                "category": it_category,
            },
        )

        Reminder.objects.get_or_create(
            user=user,
            job=job,
            defaults={"remind_on": timezone.localdate() + timedelta(days=2)},
        )

        interview_round, _ = InterviewRound.objects.get_or_create(
            user=user,
            job=job,
            round_type=InterviewRound.ROUND_TECHNICAL,
            date=timezone.localdate() - timedelta(days=1),
            defaults={"notes": "Focus on system design and ORM performance."},
        )

        InterviewQuestion.objects.get_or_create(
            user=user,
            interview_round=interview_round,
            question_text="How does Django queryset evaluation work?",
            defaults={
                "answer": "Querysets are lazy and evaluate when consumed.",
                "difficulty": InterviewQuestion.DIFFICULTY_MEDIUM,
                "topic_tag": "Django",
            },
        )

        log_activity(user, job, "Sample data seeded")
        self.stdout.write(self.style.SUCCESS(f"Sample data ready for user: {username}"))
