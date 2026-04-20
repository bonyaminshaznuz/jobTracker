from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView
from mimetypes import guess_type
from pathlib import Path

from interviews.models import InterviewRound
from jobs.forms import CVForm, CategoryForm, CoverLetterUploadForm, JobApplicationForm, JobFilterForm, JobStatusForm, NoteForm
from jobs.models import ActivityLog, CV, Category, JobApplication, Note, Reminder, log_activity


class UserQuerysetMixin:
	def get_queryset(self):
		return super().get_queryset().filter(user=self.request.user)


class JobListView(LoginRequiredMixin, ListView):
	model = JobApplication
	template_name = "jobs/job_list.html"
	context_object_name = "jobs"
	paginate_by = 10

	def get_queryset(self):
		queryset = (
			JobApplication.objects.filter(user=self.request.user)
			.select_related("category", "cv")
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

		new_cv_file = form.cleaned_data.get("new_cv_file")
		new_cv_name = form.cleaned_data.get("new_cv_name")
		new_cv_version = form.cleaned_data.get("new_cv_version")
		new_cover_letter_file = form.cleaned_data.get("new_cover_letter_file")
		selected_cv = form.cleaned_data.get("cv")

		if new_cover_letter_file:
			form.instance.cover_letter_file = new_cover_letter_file

		if new_cv_file and new_cv_name and new_cv_version:
			cv = CV.objects.create(
				user=self.request.user,
				name=new_cv_name,
				version=new_cv_version,
				file=new_cv_file,
			)
			form.instance.cv = cv

		response = super().form_valid(form)
		self._upsert_reminder(form.cleaned_data.get("reminder_date"))
		log_activity(self.request.user, self.object, "Job application created")
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
		response = super().form_valid(form)
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
		return response

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["status_form"] = JobStatusForm(initial={"status": self.object.status})
		context["cover_letter_upload_form"] = CoverLetterUploadForm()
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
		for activity in ActivityLog.objects.filter(user=self.request.user, job=job).order_by("created_at"):
			status_label = self._format_status_event(activity.event)
			if status_label:
				status_activities.append({"status": status_label, "created_at": activity.created_at})
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
		uploaded_cv_file = request.FILES.get("file")
		uploaded_cover_file = request.FILES.get("cover_letter_file")
		selected_cv_id = request.POST.get("cv")

		if uploaded_cover_file and not uploaded_cv_file:
			if job.cover_letter_file:
				job.cover_letter_file.delete(save=False)
			job.cover_letter_file = uploaded_cover_file
			job.save(update_fields=["cover_letter_file", "updated_at"])
			log_activity(request.user, job, "Cover letter uploaded")
			messages.success(request, "Cover letter uploaded and attached to the job.")
			return redirect("jobs:update", pk=job.pk)

		form = CVForm(request.POST, request.FILES, user=request.user)
		if form.is_valid():
			cv = form.save(commit=False)
			cv.user = request.user
			cv.save()
			job.cv = cv
			if uploaded_cover_file:
				if job.cover_letter_file:
					job.cover_letter_file.delete(save=False)
				job.cover_letter_file = uploaded_cover_file
				job.save(update_fields=["cv", "cover_letter_file", "updated_at"])
			else:
				job.save(update_fields=["cv", "updated_at"])
			log_activity(request.user, job, f"CV attached: {cv.name} ({cv.version})")
			messages.success(request, "CV uploaded and attached to the job.")
		else:
			messages.error(request, "CV upload failed. Please check the form.")
		return redirect("jobs:update", pk=job.pk)


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


class CVListView(LoginRequiredMixin, ListView):
	model = CV
	template_name = "jobs/cv_list.html"
	context_object_name = "cvs"

	def get_queryset(self):
		return CV.objects.filter(user=self.request.user)


class CVCreateView(LoginRequiredMixin, CreateView):
	model = CV
	form_class = CVForm
	template_name = "jobs/cv_form.html"
	success_url = reverse_lazy("jobs:cv-list")

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs["user"] = self.request.user
		return kwargs

	def form_valid(self, form):
		form.instance.user = self.request.user
		messages.success(self.request, "CV uploaded.")
		return super().form_valid(form)


class CVUpdateView(LoginRequiredMixin, UserQuerysetMixin, UpdateView):
	model = CV
	form_class = CVForm
	template_name = "jobs/cv_form.html"
	success_url = reverse_lazy("jobs:cv-list")

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs["user"] = self.request.user
		return kwargs

	def form_valid(self, form):
		messages.success(self.request, "CV updated.")
		return super().form_valid(form)


class CVDeleteView(LoginRequiredMixin, UserQuerysetMixin, DeleteView):
	model = CV
	template_name = "jobs/cv_confirm_delete.html"
	success_url = reverse_lazy("jobs:cv-list")

	def form_valid(self, form):
		messages.success(self.request, "CV deleted.")
		return super().form_valid(form)


class CVPreviewView(LoginRequiredMixin, UserQuerysetMixin, View):
	def get(self, request, pk, file_type):
		cv = get_object_or_404(CV, pk=pk, user=request.user)
		if file_type == "file":
			file_field = cv.file
		else:
			raise Http404("Unsupported file type.")

		if not file_field:
			messages.error(request, "No file available for preview.")
			return redirect("jobs:cv-list")

		if not file_field.storage.exists(file_field.name):
			messages.error(request, "This file is missing from storage. Upload it again to preview it.")
			return redirect("jobs:cv-list")

		file_field.open("rb")
		content_type, _ = guess_type(file_field.name)
		try:
			response = FileResponse(file_field, content_type=content_type or "application/octet-stream")
			response["Content-Disposition"] = f'inline; filename="{Path(file_field.name).name}"'
			return response
		except FileNotFoundError:
			messages.error(request, "This file is missing from storage. Upload it again to preview it.")
			return redirect("jobs:cv-list")


class JobCoverLetterPreviewView(LoginRequiredMixin, UserQuerysetMixin, View):
	def get(self, request, pk):
		job = get_object_or_404(JobApplication, pk=pk, user=request.user)
		file_field = job.cover_letter_file
		if not file_field:
			messages.error(request, "No cover letter available for preview.")
			return redirect("jobs:detail", pk=job.pk)

		if not file_field.storage.exists(file_field.name):
			messages.error(request, "This cover letter is missing from storage. Upload it again to preview it.")
			return redirect("jobs:detail", pk=job.pk)

		file_field.open("rb")
		content_type, _ = guess_type(file_field.name)
		try:
			response = FileResponse(file_field, content_type=content_type or "application/octet-stream")
			response["Content-Disposition"] = f'inline; filename="{Path(file_field.name).name}"'
			return response
		except FileNotFoundError:
			messages.error(request, "This cover letter is missing from storage. Upload it again to preview it.")
			return redirect("jobs:detail", pk=job.pk)


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
