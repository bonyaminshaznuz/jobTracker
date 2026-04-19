from django.contrib.auth import get_user_model
from django.db import models

from jobs.models import JobApplication, log_activity

User = get_user_model()


class InterviewRound(models.Model):
	ROUND_HR = "hr"
	ROUND_TECHNICAL = "technical"
	ROUND_FINAL = "final"
	ROUND_CHOICES = [
		(ROUND_HR, "HR"),
		(ROUND_TECHNICAL, "Technical"),
		(ROUND_FINAL, "Final"),
	]

	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="interview_rounds")
	job = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name="interview_rounds")
	round_type = models.CharField(max_length=20, choices=ROUND_CHOICES)
	date = models.DateField()
	notes = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-date", "-created_at"]

	def __str__(self):
		return f"{self.get_round_type_display()} - {self.job}"

	def save(self, *args, **kwargs):
		is_new = self.pk is None
		super().save(*args, **kwargs)
		if is_new:
			log_activity(self.user, self.job, f"Interview added: {self.get_round_type_display()} round")


class InterviewQuestion(models.Model):
	DIFFICULTY_EASY = "easy"
	DIFFICULTY_MEDIUM = "medium"
	DIFFICULTY_HARD = "hard"
	DIFFICULTY_CHOICES = [
		(DIFFICULTY_EASY, "Easy"),
		(DIFFICULTY_MEDIUM, "Medium"),
		(DIFFICULTY_HARD, "Hard"),
	]

	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="interview_questions")
	interview_round = models.ForeignKey(
		InterviewRound,
		on_delete=models.CASCADE,
		related_name="questions",
	)
	question_text = models.TextField()
	answer = models.TextField(blank=True)
	difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default=DIFFICULTY_MEDIUM)
	topic_tag = models.CharField(max_length=100, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self):
		return self.question_text[:50]
