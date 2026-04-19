from django import forms

from interviews.models import InterviewQuestion, InterviewRound


BASE_INPUT_CLASS = (
    "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm "
    "focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
)


def apply_input_classes(form):
    for field in form.fields.values():
        css = BASE_INPUT_CLASS
        if isinstance(field.widget, forms.Textarea):
            css = BASE_INPUT_CLASS + " min-h-24"
        existing = field.widget.attrs.get("class", "")
        field.widget.attrs["class"] = f"{existing} {css}".strip()
        field.widget.attrs.setdefault("placeholder", field.label)


class InterviewRoundForm(forms.ModelForm):
    class Meta:
        model = InterviewRound
        fields = ["round_type", "date", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["round_type"].choices = [("", "Select round type")] + list(InterviewRound.ROUND_CHOICES)
        apply_input_classes(self)


class InterviewQuestionForm(forms.ModelForm):
    class Meta:
        model = InterviewQuestion
        fields = ["question_text", "answer", "difficulty", "topic_tag"]
        widgets = {
            "question_text": forms.Textarea(attrs={"rows": 2}),
            "answer": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["difficulty"].choices = [("", "Select difficulty")] + list(InterviewQuestion.DIFFICULTY_CHOICES)
        apply_input_classes(self)
