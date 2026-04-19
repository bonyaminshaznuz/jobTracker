from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User


BASE_INPUT_CLASS = (
    "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm "
    "focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
)


def apply_input_classes(form):
    for name, field in form.fields.items():
        css = BASE_INPUT_CLASS
        if isinstance(field.widget, forms.CheckboxInput):
            css = "h-4 w-4 rounded border-slate-300 text-slate-700 focus:ring-slate-300"

        existing = field.widget.attrs.get("class", "")
        field.widget.attrs["class"] = f"{existing} {css}".strip()
        if not isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs.setdefault("placeholder", field.label)


class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_input_classes(self)


class UserLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_input_classes(self)
