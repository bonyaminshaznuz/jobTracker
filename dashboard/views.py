from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.utils import timezone
from django.views.generic import TemplateView

from jobs.models import ActivityLog, JobApplication, Reminder


class DashboardView(LoginRequiredMixin, TemplateView):
	template_name = "dashboard/index.html"

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		user = self.request.user
		total = JobApplication.objects.filter(user=user).count()
		interviews = JobApplication.objects.filter(
			user=user,
			status__in=[
				JobApplication.STATUS_INTERVIEW,
				JobApplication.STATUS_TECH_TEST,
				JobApplication.STATUS_HR_INTERVIEW,
			],
		).count()
		offers = JobApplication.objects.filter(user=user, status=JobApplication.STATUS_OFFER).count()
		rejected = JobApplication.objects.filter(user=user, status=JobApplication.STATUS_REJECTED).count()

		interview_rate = (interviews / total * 100) if total else 0
		success_rate = (offers / total * 100) if total else 0

		reminders = Reminder.objects.filter(
			user=user,
			completed=False,
			remind_on__lte=timezone.localdate(),
		).select_related("job")

		recent_activity = ActivityLog.objects.filter(user=user).select_related("job")[:10]
		status_breakdown = JobApplication.objects.filter(user=user).values("status").annotate(count=Count("id"))

		context.update(
			{
				"total_applications": total,
				"interview_count": interviews,
				"offer_count": offers,
				"rejection_count": rejected,
				"interview_rate": round(interview_rate, 2),
				"success_rate": round(success_rate, 2),
				"reminders": reminders,
				"recent_activity": recent_activity,
				"status_breakdown": status_breakdown,
			}
		)
		return context
