import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, SuspiciousFileOperation, ValidationError
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.db import transaction
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from interviews.models import InterviewRound
from jobs.forms import CategoryForm, JobApplicationForm, JobFilterForm, JobStatusForm, NoteForm
from jobs.models import (
	ActivityLog,
	Category,
	JobApplication,
	Note,
	Reminder,
	log_activity,
	normalize_storage_name,
)

logger = logging.getLogger(__name__)


class UserQuerysetMixin:
	def get_queryset(self):
		return super().get_queryset().filter(user=self.request.user)


def _delete_file_after_commit(storage, file_name):
	if not storage:
		return
	file_name = normalize_storage_name(file_name)
	if not file_name:
		return

	def _delete_if_exists(storage_obj, name):
		try:
			if storage_obj.exists(name):
				storage_obj.delete(name)
		except (OSError, SuspiciousFileOperation, ValueError):
			# Invalid legacy file paths should not break request lifecycle.
			return

	transaction.on_commit(lambda storage=storage, file_name=file_name: _delete_if_exists(storage, file_name))


class JobListView(LoginRequiredMixin, ListView):
	model = JobApplication
	template_name = "jobs/job_list.html"
	context_object_name = "jobs"
	paginate_by = 10

	def get_queryset(self):
		queryset = (
			JobApplication.objects.filter(user=self.request.user)
			.select_related("category")
			.order_by("-date_applied", "-created_at")
		)
		self.filter_form = JobFilterForm(self.request.GET or None, user=self.request.user)
		return self.filter_form.apply(queryset)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["filter_form"] = self.filter_form
		return context


class JobCreateView(LoginRequiredMixin, CreateView):
	model = JobApplication
	form_class = JobApplicationForm
	template_name = "jobs/job_form.html"

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs["user"] = self.request.user
		return kwargs

	def form_valid(self, form):
		form.instance.user = self.request.user
		response = super().form_valid(form)
		self._upsert_reminder(form.cleaned_data.get("reminder_date"))
		log_activity(self.request.user, self.object, f"Status updated: {self.object.get_status_display()}")
		messages.success(self.request, "Job application added.")
		return response

	def _upsert_reminder(self, reminder_date):
		if reminder_date:
			Reminder.objects.update_or_create(
				user=self.request.user,
				job=self.object,
				defaults={"remind_on": reminder_date, "completed": False},
			)

	def get_success_url(self):
		return reverse("jobs:detail", kwargs={"pk": self.object.pk})


class JobUpdateView(LoginRequiredMixin, UserQuerysetMixin, UpdateView):
	model = JobApplication
	form_class = JobApplicationForm
	template_name = "jobs/job_form.html"

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs["user"] = self.request.user
		return kwargs

	def get_initial(self):
		initial = super().get_initial()
		reminder = Reminder.objects.filter(job=self.object, user=self.request.user).first()
		if reminder:
			initial["reminder_date"] = reminder.remind_on
		return initial

	def form_valid(self, form):
		previous_job = self.get_object()
		previous_cv = previous_job.cv_file
		previous_cv_name = previous_cv.name if previous_cv and previous_cv.name else ""
		previous_cv_storage = previous_cv.storage if previous_cv_name else None
		previous_cover_letter = previous_job.cover_letter_file
		previous_cover_letter_name = previous_cover_letter.name if previous_cover_letter and previous_cover_letter.name else ""
		previous_cover_letter_storage = previous_cover_letter.storage if previous_cover_letter_name else None

		try:
			with transaction.atomic():
				self.object = form.save(commit=False)

				# Keep existing attachment names unless a replacement file was posted.
				if "cv_file" not in self.request.FILES:
					self.object.cv_file = previous_cv_name or None
				if "cover_letter_file" not in self.request.FILES:
					self.object.cover_letter_file = previous_cover_letter_name or None

				self.object.save()
				form.save_m2m()
				if previous_cv_name and previous_cv_name != (self.object.cv_file.name if self.object.cv_file else ""):
					_delete_file_after_commit(previous_cv_storage, previous_cv_name)
				if previous_cover_letter_name and previous_cover_letter_name != (self.object.cover_letter_file.name if self.object.cover_letter_file else ""):
					_delete_file_after_commit(previous_cover_letter_storage, previous_cover_letter_name)
				reminder_date = form.cleaned_data.get("reminder_date")
				if reminder_date:
					Reminder.objects.update_or_create(
						user=self.request.user,
						job=self.object,
						defaults={"remind_on": reminder_date, "completed": False},
					)
				else:
					Reminder.objects.filter(user=self.request.user, job=self.object).delete()
				log_activity(self.request.user, self.object, "Job application updated")
				messages.success(self.request, "Job application updated.")
			return redirect(self.get_success_url())
		except Exception:
			logger.exception("Failed to update job application", extra={"job_id": self.object.pk, "user_id": self.request.user.pk})
			form.add_error(None, "Could not update the job right now. Please try again.")
			messages.error(self.request, "Could not update the job right now. Please try again.")
			return self.form_invalid(form)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["status_form"] = JobStatusForm(initial={"status": self.object.status})
		return context

	def get_success_url(self):
		return reverse("jobs:detail", kwargs={"pk": self.object.pk})


class JobDeleteView(LoginRequiredMixin, UserQuerysetMixin, DeleteView):
	model = JobApplication
	template_name = "jobs/job_confirm_delete.html"
	success_url = reverse_lazy("jobs:list")

	def form_valid(self, form):
		messages.success(self.request, "Job application deleted.")
		return super().form_valid(form)


class JobDetailView(LoginRequiredMixin, UserQuerysetMixin, DetailView):
	model = JobApplication
	template_name = "jobs/job_detail.html"
	context_object_name = "job"

	def _format_status_event(self, event):
		if not event.startswith("Status updated:"):
			return None

		remainder = event.split(":", 1)[1].strip()
		if "->" in remainder:
			return remainder.split("->", 1)[1].strip()
		return remainder

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		job = self.object
		status_activities = []
		seen_applied = False
		for activity in ActivityLog.objects.filter(user=self.request.user, job=job).order_by("created_at"):
			status_label = self._format_status_event(activity.event)
			if status_label:
				if status_label.strip().lower() == JobApplication.STATUS_APPLIED:
					seen_applied = True
				status_activities.append({"status": status_label, "created_at": activity.created_at})
		if not seen_applied:
			status_activities.insert(
				0,
				{
					"status": job.get_status_display() if job.status == JobApplication.STATUS_APPLIED else "Applied",
					"created_at": job.created_at,
				},
			)
		context.update(
			{
				"status_form": JobStatusForm(initial={"status": job.status}),
				"note_form": NoteForm(),
				"notes": Note.objects.filter(user=self.request.user, job=job),
				"interview_rounds": InterviewRound.objects.filter(user=self.request.user, job=job).prefetch_related(
					"questions"
				),
				"activities": status_activities,
			}
		)
		return context


class JobStatusUpdateView(LoginRequiredMixin, View):
	def post(self, request, job_pk):
		job = get_object_or_404(JobApplication, pk=job_pk, user=request.user)
		form = JobStatusForm(request.POST)
		if form.is_valid():
			new_status = form.cleaned_data["status"]
			if new_status != job.status:
				previous = job.get_status_display()
				job.status = new_status
				job.save(update_fields=["status", "updated_at"])
				log_activity(request.user, job, f"Status updated: {previous} -> {job.get_status_display()}")
				messages.success(request, "Status updated.")
		else:
			messages.error(request, "Could not update status.")

		next_url = request.POST.get("next")
		if next_url:
			return redirect(next_url)
		return redirect("jobs:detail", pk=job.pk)


class JobInlineCVUploadView(LoginRequiredMixin, View):
	def post(self, request, job_pk):
		job = get_object_or_404(JobApplication, pk=job_pk, user=request.user)
		uploaded_cv_file = request.FILES.get("cv_file") or request.FILES.get("file")
		uploaded_cover_file = request.FILES.get("cover_letter_file")

		if uploaded_cv_file and not uploaded_cover_file:
			previous_cv = job.cv_file
			previous_cv_name = previous_cv.name if previous_cv and previous_cv.name else ""
			previous_cv_storage = previous_cv.storage if previous_cv_name else None
			with transaction.atomic():
				job.cv_file = uploaded_cv_file
				job.save(update_fields=["cv_file", "updated_at"])
				if previous_cv_name and previous_cv_name != job.cv_file.name:
					_delete_file_after_commit(previous_cv_storage, previous_cv_name)
			log_activity(request.user, job, "CV uploaded")
			messages.success(request, "CV uploaded and attached to the job.")
			return redirect("jobs:update", pk=job.pk)

		if uploaded_cover_file and not uploaded_cv_file:
			previous_cover_letter = job.cover_letter_file
			previous_cover_letter_name = previous_cover_letter.name if previous_cover_letter and previous_cover_letter.name else ""
			previous_cover_letter_storage = previous_cover_letter.storage if previous_cover_letter_name else None
			with transaction.atomic():
				job.cover_letter_file = uploaded_cover_file
				job.save(update_fields=["cover_letter_file", "updated_at"])
				if previous_cover_letter_name and previous_cover_letter_name != job.cover_letter_file.name:
					_delete_file_after_commit(previous_cover_letter_storage, previous_cover_letter_name)
			log_activity(request.user, job, "Cover letter uploaded")
			messages.success(request, "Cover letter uploaded and attached to the job.")
			return redirect("jobs:update", pk=job.pk)

		if uploaded_cv_file and uploaded_cover_file:
			previous_cv = job.cv_file
			previous_cv_name = previous_cv.name if previous_cv and previous_cv.name else ""
			previous_cv_storage = previous_cv.storage if previous_cv_name else None
			previous_cover_letter = job.cover_letter_file
			previous_cover_letter_name = previous_cover_letter.name if previous_cover_letter and previous_cover_letter.name else ""
			previous_cover_letter_storage = previous_cover_letter.storage if previous_cover_letter_name else None
			with transaction.atomic():
				job.cv_file = uploaded_cv_file
				job.cover_letter_file = uploaded_cover_file
				job.save(update_fields=["cv_file", "cover_letter_file", "updated_at"])
				if previous_cv_name and previous_cv_name != job.cv_file.name:
					_delete_file_after_commit(previous_cv_storage, previous_cv_name)
				if previous_cover_letter_name and previous_cover_letter_name != job.cover_letter_file.name:
					_delete_file_after_commit(previous_cover_letter_storage, previous_cover_letter_name)
			log_activity(request.user, job, "CV and cover letter uploaded")
			messages.success(request, "CV and cover letter uploaded and attached to the job.")
		else:
			messages.error(request, "No file selected.")
		return redirect("jobs:update", pk=job.pk)


# ---------------------------------------------------------------------------
# Shared helper for file views
# ---------------------------------------------------------------------------

_UPLOAD_PREFIXES = [
	("cvs", "cv_file"),
	("cover_letters", "cover_letter_file"),
]


def _can_access_job_file(request_user, job):
	"""Allow file access to owner, staff, or superuser users."""
	return bool(
		request_user.is_authenticated
		and (job.user_id == request_user.id or request_user.is_staff or request_user.is_superuser)
	)


def _open_file_field(job, field_name):
	"""
	Generic helper to open any FileField on a JobApplication for reading.

	Handles self-healing of duplicated upload-path prefixes automatically
	(e.g. ``cvs/cvs/file.pdf`` → ``cvs/file.pdf``) and persists the
	corrected path to the DB so future requests are fast.

	Args:
	    job: JobApplication instance
	    field_name: "cv_file" or "cover_letter_file"

	Raises FileNotFoundError if the file cannot be found under any candidate path.
	"""
	file_field = getattr(job, field_name)
	original_name = file_field.name or ""

	candidates = [original_name]

	# Build de-duplicated alternative if a doubled prefix is detected.
	for prefix, fname in _UPLOAD_PREFIXES:
		if fname == field_name:
			doubled = f"{prefix}/{prefix}/"
			if original_name.startswith(doubled):
				candidates.append(prefix + "/" + original_name[len(doubled):])
			break

	last_exc = None
	for candidate in candidates:
		try:
			file_field.name = candidate
			file_field.open("rb")

			# Success — persist the healed path if it changed.
			if candidate != original_name:
				logger.info(
					"[FILE-HEAL] Auto-repaired %s for job #%s: %r -> %r",
					field_name, job.pk, original_name, candidate,
				)
				JobApplication.objects.filter(pk=job.pk).update(**{field_name: candidate})

			return file_field

		except (FileNotFoundError, OSError) as exc:
			logger.warning(
				"[FILE-HEAL] Could not open %r (%s) for job #%s: %s",
				candidate, field_name, job.pk, exc,
			)
			last_exc = exc

	# Restore original name so the model is not left in a dirty state.
	file_field.name = original_name
	raise FileNotFoundError(
		f"{field_name} not found for job #{job.pk}. Tried: {candidates}"
	) from last_exc


def _get_content_type(filename):
	"""Return the MIME type based on file extension."""
	name = (filename or "").lower()
	if name.endswith(".pdf"):
		return "application/pdf"
	if name.endswith(".docx"):
		return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
	if name.endswith(".doc"):
		return "application/msword"
	return "application/octet-stream"


# ---------------------------------------------------------------------------
# CV preview / download views
# ---------------------------------------------------------------------------


class JobFilePreviewView(LoginRequiredMixin, View):
	def get(self, request, job_id):
		job = get_object_or_404(JobApplication, pk=job_id)
		if not _can_access_job_file(request.user, job):
			raise PermissionDenied

		if not job.cv_file:
			messages.error(request, "No CV attached to this job.")
			return redirect("jobs:detail", pk=job.pk)

		try:
			_open_file_field(job, "cv_file")
		except FileNotFoundError:
			messages.error(request, "The CV file could not be found on the server. Please re-upload it.")
			return redirect("jobs:detail", pk=job.pk)

		filename = job.cv_filename or "cv.pdf"
		response = FileResponse(job.cv_file.file, content_type=_get_content_type(filename))
		response["Content-Disposition"] = f'inline; filename="{filename}"'
		return response


class JobFileDownloadView(LoginRequiredMixin, View):
	def get(self, request, job_id):
		job = get_object_or_404(JobApplication, pk=job_id)
		if not _can_access_job_file(request.user, job):
			raise PermissionDenied

		if not job.cv_file:
			messages.error(request, "No CV attached to this job.")
			return redirect("jobs:detail", pk=job.pk)

		try:
			_open_file_field(job, "cv_file")
		except FileNotFoundError:
			messages.error(request, "The CV file could not be found on the server. Please re-upload it.")
			return redirect("jobs:detail", pk=job.pk)

		filename = job.cv_filename or "cv.pdf"
		response = FileResponse(job.cv_file.file, content_type=_get_content_type(filename))
		response["Content-Disposition"] = f'attachment; filename="{filename}"'
		return response


# ---------------------------------------------------------------------------
# Cover letter preview / download views
# ---------------------------------------------------------------------------


class JobCoverLetterPreviewView(LoginRequiredMixin, View):
	def get(self, request, job_id):
		job = get_object_or_404(JobApplication, pk=job_id)
		if not _can_access_job_file(request.user, job):
			raise PermissionDenied

		if not job.cover_letter_file:
			messages.error(request, "No cover letter attached to this job.")
			return redirect("jobs:detail", pk=job.pk)

		try:
			_open_file_field(job, "cover_letter_file")
		except FileNotFoundError:
			messages.error(request, "The cover letter file could not be found on the server. Please re-upload it.")
			return redirect("jobs:detail", pk=job.pk)

		filename = job.cover_letter_filename or "cover_letter.pdf"
		response = FileResponse(job.cover_letter_file.file, content_type=_get_content_type(filename))
		response["Content-Disposition"] = f'inline; filename="{filename}"'
		return response


class JobCoverLetterDownloadView(LoginRequiredMixin, View):
	def get(self, request, job_id):
		job = get_object_or_404(JobApplication, pk=job_id)
		if not _can_access_job_file(request.user, job):
			raise PermissionDenied

		if not job.cover_letter_file:
			messages.error(request, "No cover letter attached to this job.")
			return redirect("jobs:detail", pk=job.pk)

		try:
			_open_file_field(job, "cover_letter_file")
		except FileNotFoundError:
			messages.error(request, "The cover letter file could not be found on the server. Please re-upload it.")
			return redirect("jobs:detail", pk=job.pk)

		filename = job.cover_letter_filename or "cover_letter.pdf"
		response = FileResponse(job.cover_letter_file.file, content_type=_get_content_type(filename))
		response["Content-Disposition"] = f'attachment; filename="{filename}"'
		return response


class NoteCreateView(LoginRequiredMixin, View):
	def post(self, request, job_pk):
		job = get_object_or_404(JobApplication, pk=job_pk, user=request.user)
		form = NoteForm(request.POST)
		if form.is_valid():
			note = form.save(commit=False)
			note.user = request.user
			note.job = job
			note.save()
			log_activity(request.user, job, "Note added")
			messages.success(request, "Note added.")
		else:
			messages.error(request, "Could not add note.")
		return redirect("jobs:detail", pk=job.pk)


class CategoryListView(LoginRequiredMixin, ListView):
	model = Category
	template_name = "jobs/category_list.html"
	context_object_name = "categories"

	def get_queryset(self):
		return Category.objects.filter(user=self.request.user)


class CategoryCreateView(LoginRequiredMixin, CreateView):
	model = Category
	form_class = CategoryForm
	template_name = "jobs/category_form.html"
	success_url = reverse_lazy("jobs:category-list")

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs["user"] = self.request.user
		return kwargs

	def form_valid(self, form):
		form.instance.user = self.request.user
		messages.success(self.request, "Category created.")
		return super().form_valid(form)


class CategoryUpdateView(LoginRequiredMixin, UserQuerysetMixin, UpdateView):
	model = Category
	form_class = CategoryForm
	template_name = "jobs/category_form.html"
	success_url = reverse_lazy("jobs:category-list")

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs["user"] = self.request.user
		return kwargs

	def form_valid(self, form):
		messages.success(self.request, "Category updated.")
		return super().form_valid(form)


class CategoryDeleteView(LoginRequiredMixin, UserQuerysetMixin, DeleteView):
	model = Category
	template_name = "jobs/category_confirm_delete.html"
	success_url = reverse_lazy("jobs:category-list")

	def post(self, request, *args, **kwargs):
		self.object = self.get_object()
		try:
			self.object.delete()
		except ValidationError as exc:
			messages.error(request, exc.messages[0])
		else:
			messages.success(request, "Category deleted.")
		return redirect(self.success_url)


class KanbanView(LoginRequiredMixin, TemplateView):
	template_name = "jobs/kanban.html"

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		user_jobs = JobApplication.objects.filter(user=self.request.user)
		context["columns"] = {
			"Applied": user_jobs.filter(status=JobApplication.STATUS_APPLIED),
			"Screening": user_jobs.filter(status=JobApplication.STATUS_SCREENING),
			"Interview": user_jobs.filter(
				status__in=[
					JobApplication.STATUS_INTERVIEW,
					JobApplication.STATUS_TECH_TEST,
					JobApplication.STATUS_HR_INTERVIEW,
				]
			),
			"Offer": user_jobs.filter(status=JobApplication.STATUS_OFFER),
			"Rejected": user_jobs.filter(status=JobApplication.STATUS_REJECTED),
		}
		return context
