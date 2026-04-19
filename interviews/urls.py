from django.urls import path

from interviews.views import (
    InterviewQuestionCreateView,
    InterviewQuestionDeleteView,
    InterviewQuestionUpdateView,
    InterviewRoundCreateView,
    InterviewRoundDeleteView,
    InterviewRoundUpdateView,
)

app_name = "interviews"

urlpatterns = [
    path("jobs/<int:job_pk>/rounds/new/", InterviewRoundCreateView.as_view(), name="round-create"),
    path("rounds/<int:pk>/edit/", InterviewRoundUpdateView.as_view(), name="round-update"),
    path("rounds/<int:pk>/delete/", InterviewRoundDeleteView.as_view(), name="round-delete"),
    path("rounds/<int:round_pk>/questions/new/", InterviewQuestionCreateView.as_view(), name="question-create"),
    path("questions/<int:pk>/edit/", InterviewQuestionUpdateView.as_view(), name="question-update"),
    path("questions/<int:pk>/delete/", InterviewQuestionDeleteView.as_view(), name="question-delete"),
]
