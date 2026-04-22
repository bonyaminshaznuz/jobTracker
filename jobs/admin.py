from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from jobs.models import ActivityLog, Category, JobApplication, Note, Reminder


class JobApplicationAdminForm(forms.ModelForm):
	class Meta:
		model = JobApplication
		fields = "__all__"
		widgets = {
			"cv_file": forms.FileInput(),
			"cover_letter_file": forms.FileInput(),
		}


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
	form = JobApplicationAdminForm
	readonly_fields = ("cv_actions", "cover_letter_actions")
	list_display = ("company_name", "job_title", "user", "status", "date_applied")
	search_fields = ("company_name", "job_title", "user__email", "user__username")
	list_filter = ("status", "location", "date_applied")

	@admin.display(description="CV preview/download")
	def cv_actions(self, obj):
		if not obj or not obj.pk or not obj.cv_file:
			return "No CV attached"

		preview_url = reverse("jobs:file-preview", kwargs={"job_id": obj.pk})
		download_url = reverse("jobs:file-download", kwargs={"job_id": obj.pk})
		return format_html(
			'<a href="{}" target="_blank" rel="noopener noreferrer">Preview CV</a> | '
			'<a href="{}">Download CV</a>',
			preview_url,
			download_url,
		)

	@admin.display(description="Cover letter preview/download")
	def cover_letter_actions(self, obj):
		if not obj or not obj.pk or not obj.cover_letter_file:
			return "No cover letter attached"

		preview_url = reverse("jobs:cover-letter-preview", kwargs={"job_id": obj.pk})
		download_url = reverse("jobs:cover-letter-download", kwargs={"job_id": obj.pk})
		return format_html(
			'<a href="{}" target="_blank" rel="noopener noreferrer">Preview cover letter</a> | '
			'<a href="{}">Download cover letter</a>',
			preview_url,
			download_url,
		)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
	list_display = ("name", "user", "created_at")
	search_fields = ("name", "user__email", "user__username")


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
	list_display = ("job", "user", "created_at")
	search_fields = ("content", "user__email", "job__company_name", "job__job_title")


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
	list_display = ("job", "user", "remind_on", "completed")
	list_filter = ("completed", "remind_on")


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
	list_display = ("job", "user", "event", "created_at")
	search_fields = ("event", "user__email", "job__company_name", "job__job_title")
