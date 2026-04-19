from django.contrib import admin

from interviews.models import InterviewQuestion, InterviewRound

admin.site.register(InterviewRound)
admin.site.register(InterviewQuestion)

# Register your models here.
