from django import forms
from django.db.models import Q

from jobs.models import CV, Category, JobApplication, Note


BASE_INPUT_CLASS = (
    "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm "
    "focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
)


def apply_input_classes(form):
    for field in form.fields.values():
        widget = field.widget
        css = BASE_INPUT_CLASS
        if isinstance(widget, forms.Textarea):
            css = BASE_INPUT_CLASS + " min-h-24 resize-y"
        if isinstance(widget, (forms.ClearableFileInput, forms.FileInput)):
            css = "block w-full text-sm text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-slate-800 file:px-3 file:py-2 file:text-white hover:file:bg-slate-900"
        if isinstance(widget, forms.CheckboxInput):
            css = "h-4 w-4 rounded border-slate-300 text-slate-700 focus:ring-slate-300"

        existing = widget.attrs.get("class", "")
        widget.attrs["class"] = f"{existing} {css}".strip()
        if not isinstance(widget, (forms.CheckboxInput, forms.ClearableFileInput)):
            widget.attrs.setdefault("placeholder", field.label)


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        apply_input_classes(self)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        exists = Category.objects.filter(user=self.user, name__iexact=name)
        if self.instance.pk:
            exists = exists.exclude(pk=self.instance.pk)
        if exists.exists():
            raise forms.ValidationError("You already have a category with this name.")
        return name


class JobApplicationForm(forms.ModelForm):
    reminder_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Optional follow-up reminder date",
    )
    new_cv_file = forms.FileField(required=False, label="Upload CV")
    new_cover_letter_file = forms.FileField(required=False, label="Upload cover letter")

    class Meta:
        model = JobApplication
        fields = [
            "company_name",
            "job_title",
            "job_post_url",
            "location",
            "city_name",
            "salary",
            "job_description",
            "date_applied",
            "status",
            "category",
        ]
        widgets = {
            "date_applied": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user:
            self.fields["category"].queryset = Category.objects.filter(user=user)
        self.fields["category"].empty_label = "Select category"
        self.fields["location"].choices = [("", "Select type")] + list(JobApplication.LOCATION_CHOICES)
        apply_input_classes(self)

    def clean(self):
        cleaned_data = super().clean()
        new_cv_file = cleaned_data.get("new_cv_file")
        new_cover_letter_file = cleaned_data.get("new_cover_letter_file")
        if not self.instance.pk and not new_cv_file:
            self.add_error("new_cv_file", "Upload a CV file for this job application.")

        cleaned_data["new_cover_letter_file"] = new_cover_letter_file
        return cleaned_data


class CVForm(forms.ModelForm):
    class Meta:
        model = CV
        fields = ["name", "version", "file"]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        apply_input_classes(self)

    def clean(self):
        cleaned_data = super().clean()
        name = (cleaned_data.get("name") or "").strip()
        version = (cleaned_data.get("version") or "").strip()
        user = getattr(self, "user", None)

        if user and name and version:
            exists = CV.objects.filter(user=user, name__iexact=name, version__iexact=version)
            if self.instance.pk:
                exists = exists.exclude(pk=self.instance.pk)
            if exists.exists():
                raise forms.ValidationError("You already have a CV with this name and version.")

        cleaned_data["name"] = name
        cleaned_data["version"] = version
        return cleaned_data


class CoverLetterUploadForm(forms.Form):
    cover_letter_file = forms.FileField(required=False, label="Upload a cover letter")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_input_classes(self)


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_input_classes(self)


class JobFilterForm(forms.Form):
    q = forms.CharField(required=False, label="Search")
    status = forms.ChoiceField(required=False, choices=[("", "All statuses")] + JobApplication.STATUS_CHOICES)
    category = forms.ModelChoiceField(required=False, queryset=Category.objects.none())
    location = forms.ChoiceField(required=False, choices=[("", "All type")] + JobApplication.LOCATION_CHOICES)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["category"].queryset = Category.objects.filter(user=user)
        self.fields["category"].empty_label = "All category"
        apply_input_classes(self)
        self.fields["q"].widget.attrs["placeholder"] = "Search by company or title"

    def apply(self, queryset):
        if not self.is_valid():
            return queryset

        q = self.cleaned_data.get("q")
        if q:
            queryset = queryset.filter(Q(company_name__icontains=q) | Q(job_title__icontains=q))

        status = self.cleaned_data.get("status")
        if status:
            queryset = queryset.filter(status=status)

        category = self.cleaned_data.get("category")
        if category:
            queryset = queryset.filter(category=category)

        location = self.cleaned_data.get("location")
        if location:
            queryset = queryset.filter(location=location)

        return queryset


class JobStatusForm(forms.Form):
    status = forms.ChoiceField(choices=JobApplication.STATUS_CHOICES)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = [("", "Select status")] + list(JobApplication.STATUS_CHOICES)
        apply_input_classes(self)
