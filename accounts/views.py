from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView

from accounts.forms import UserRegisterForm


class SignUpView(CreateView):
	template_name = "accounts/signup.html"
	form_class = UserRegisterForm
	success_url = reverse_lazy("accounts:login")

	def form_valid(self, form):
		response = super().form_valid(form)
		messages.success(self.request, "Account created successfully. Please login.")
		return response
