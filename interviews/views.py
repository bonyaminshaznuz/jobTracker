from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, UpdateView

from interviews.forms import InterviewQuestionForm, InterviewRoundForm
from interviews.models import InterviewQuestion, InterviewRound
from jobs.models import JobApplication


class InterviewRoundCreateView(LoginRequiredMixin, CreateView):
	model = InterviewRound
	form_class = InterviewRoundForm
	template_name = "interviews/round_form.html"

	def dispatch(self, request, *args, **kwargs):
		self.job = get_object_or_404(JobApplication, pk=kwargs["job_pk"], user=request.user)
		return super().dispatch(request, *args, **kwargs)

	def form_valid(self, form):
		form.instance.user = self.request.user
		form.instance.job = self.job
		messages.success(self.request, "Interview round added.")
		return super().form_valid(form)

	def get_success_url(self):
		return reverse("jobs:detail", kwargs={"pk": self.job.pk})


class InterviewRoundUpdateView(LoginRequiredMixin, UpdateView):
	model = InterviewRound
	form_class = InterviewRoundForm
	template_name = "interviews/round_form.html"

	def get_queryset(self):
		return InterviewRound.objects.filter(user=self.request.user)

	def form_valid(self, form):
		messages.success(self.request, "Interview round updated.")
		return super().form_valid(form)

	def get_success_url(self):
		return reverse("jobs:detail", kwargs={"pk": self.object.job.pk})


class InterviewRoundDeleteView(LoginRequiredMixin, DeleteView):
	model = InterviewRound
	template_name = "interviews/round_confirm_delete.html"

	def get_queryset(self):
		return InterviewRound.objects.filter(user=self.request.user)

	def get_success_url(self):
		messages.success(self.request, "Interview round deleted.")
		return reverse("jobs:detail", kwargs={"pk": self.object.job.pk})


class InterviewQuestionCreateView(LoginRequiredMixin, CreateView):
	model = InterviewQuestion
	form_class = InterviewQuestionForm
	template_name = "interviews/question_form.html"

	def dispatch(self, request, *args, **kwargs):
		self.round = get_object_or_404(InterviewRound, pk=kwargs["round_pk"], user=request.user)
		return super().dispatch(request, *args, **kwargs)

	def form_valid(self, form):
		form.instance.user = self.request.user
		form.instance.interview_round = self.round
		messages.success(self.request, "Interview question added.")
		return super().form_valid(form)

	def get_success_url(self):
		return reverse("jobs:detail", kwargs={"pk": self.round.job.pk})


class InterviewQuestionUpdateView(LoginRequiredMixin, UpdateView):
	model = InterviewQuestion
	form_class = InterviewQuestionForm
	template_name = "interviews/question_form.html"

	def get_queryset(self):
		return InterviewQuestion.objects.filter(user=self.request.user)

	def form_valid(self, form):
		messages.success(self.request, "Interview question updated.")
		return super().form_valid(form)

	def get_success_url(self):
		return reverse("jobs:detail", kwargs={"pk": self.object.interview_round.job.pk})


class InterviewQuestionDeleteView(LoginRequiredMixin, DeleteView):
	model = InterviewQuestion
	template_name = "interviews/question_confirm_delete.html"

	def get_queryset(self):
		return InterviewQuestion.objects.filter(user=self.request.user)

	def get_success_url(self):
		messages.success(self.request, "Interview question deleted.")
		return reverse("jobs:detail", kwargs={"pk": self.object.interview_round.job.pk})
