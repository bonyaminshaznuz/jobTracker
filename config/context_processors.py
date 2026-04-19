from django.conf import settings


def auth_flags(request):
	return {
		"google_oauth_enabled": bool(getattr(settings, "GOOGLE_CLIENT_ID", "") and getattr(settings, "GOOGLE_CLIENT_SECRET", ""))
	}