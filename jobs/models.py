from django.contrib.auth import get_user_model
from django.core.exceptions import SuspiciousFileOperation, ValidationError
from django.db import models

User = get_user_model()


def validate_upload_size(file_obj):
	try:
		size = file_obj.size
	except (FileNotFoundError, OSError, SuspiciousFileOperation, ValueError):
		# Legacy rows may point to files that no longer exist in storage.
		# Do not crash unrelated form submissions.
		return

	if size > 5 * 1024 * 1024:
		raise ValidationError("File size must be less than 5MB.")


def validate_upload_extension(file_obj):
	allowed_extensions = {".pdf", ".doc", ".docx", ".txt"}
	file_name = file_obj.name.lower()
	if not any(file_name.endswith(ext) for ext in allowed_extensions):
		raise ValidationError("Only PDF, DOC, DOCX and TXT files are allowed.")


class CategoryQuerySet(models.QuerySet):
	def delete(self, *args, **kwargs):
		for category in self:
			category.delete()


class Category(models.Model):
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="categories")
	name = models.CharField(max_length=100)
	created_at = models.DateTimeField(auto_now_add=True)

	objects = CategoryQuerySet.as_manager()

	class Meta:
		ordering = ["name"]
		constraints = [
			models.UniqueConstraint(fields=["user", "name"], name="uniq_category_per_user")
		]

	def __str__(self):
		return self.name

	def delete(self, *args, **kwargs):
		if self.name == "Uncategorized":
			raise ValidationError("Default category cannot be deleted.")
		default_category, _ = Category.objects.get_or_create(
			user=self.user,
			name="Uncategorized",
		)
		self.jobs.update(category=default_category)
		super().delete(*args, **kwargs)


class JobApplication(models.Model):
	STATUS_APPLIED = "applied"
	STATUS_SCREENING = "screening"
	STATUS_INTERVIEW = "interview"
	STATUS_TECH_TEST = "technical_test"
	STATUS_HR_INTERVIEW = "hr_interview"
	STATUS_OFFER = "offer"
	STATUS_REJECTED = "rejected"

	STATUS_CHOICES = [
		(STATUS_APPLIED, "Applied"),
		(STATUS_SCREENING, "Screening"),
		(STATUS_INTERVIEW, "Interview"),
		(STATUS_TECH_TEST, "Technical Test"),
		(STATUS_HR_INTERVIEW, "HR Interview"),
		(STATUS_OFFER, "Offer"),
		(STATUS_REJECTED, "Rejected"),
	]

	LOCATION_REMOTE = "remote"
	LOCATION_HYBRID = "hybrid"
	LOCATION_ONSITE = "onsite"
	LOCATION_CHOICES = [
		(LOCATION_REMOTE, "Remote"),
		(LOCATION_HYBRID, "Hybrid"),
		(LOCATION_ONSITE, "Onsite"),
	]

	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="jobs")
	category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="jobs")
	cv_file = models.FileField(
		upload_to="cvs/",
		blank=True,
		null=True,
		validators=[validate_upload_extension, validate_upload_size],
	)
	cover_letter_file = models.FileField(
		upload_to="cover_letters/",
		blank=True,
		null=True,
		validators=[validate_upload_extension, validate_upload_size],
	)
	company_name = models.CharField(max_length=150)
	job_title = models.CharField(max_length=150)
	job_post_url = models.URLField(blank=True)
	location = models.CharField(max_length=20, choices=LOCATION_CHOICES)
	city_name = models.CharField(max_length=120, blank=True)
	salary = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
	job_description = models.TextField(blank=True)
	date_applied = models.DateField()
	status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_APPLIED)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-date_applied", "-created_at"]

	def __str__(self):
		return f"{self.company_name} - {self.job_title}"

	@property
	def is_cv_pdf(self):
		return bool(self.cv_file and self.cv_file.name.lower().endswith(".pdf"))

	@property
	def cv_filename(self):
		if not self.cv_file:
			return ""
		return self.cv_file.name.rsplit("/", 1)[-1]

	@property
	def cv_file_url(self):
		if not self.cv_file:
			return ""
		try:
			return self.cv_file.url
		except (ValueError, OSError, SuspiciousFileOperation):
			return ""

	@property
	def cover_letter_file_url(self):
		if not self.cover_letter_file:
			return ""
		try:
			return self.cover_letter_file.url
		except (ValueError, OSError, SuspiciousFileOperation):
			return ""


class Note(models.Model):
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notes")
	job = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name="notes")
	content = models.TextField()
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]


class Reminder(models.Model):
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reminders")
	job = models.OneToOneField(JobApplication, on_delete=models.CASCADE, related_name="reminder")
	remind_on = models.DateField()
	completed = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["remind_on"]


class ActivityLog(models.Model):
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="activities")
	job = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name="activities")
	event = models.CharField(max_length=200)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]


def log_activity(user, job, event):
	ActivityLog.objects.create(user=user, job=job, event=event)
