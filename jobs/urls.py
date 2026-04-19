from django.urls import path

from jobs.views import (
    CVCreateView,
    CVDeleteView,
    CVListView,
    CVPreviewView,
    CVUpdateView,
    CategoryCreateView,
    CategoryDeleteView,
    CategoryListView,
    CategoryUpdateView,
    JobCreateView,
    JobDeleteView,
    JobDetailView,
    JobInlineCVUploadView,
    JobListView,
    JobCoverLetterPreviewView,
    JobStatusUpdateView,
    JobUpdateView,
    KanbanView,
    NoteCreateView,
)

app_name = "jobs"

urlpatterns = [
    path("", JobListView.as_view(), name="list"),
    path("new/", JobCreateView.as_view(), name="create"),
    path("<int:pk>/", JobDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", JobUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", JobDeleteView.as_view(), name="delete"),
    path("<int:job_pk>/status/update/", JobStatusUpdateView.as_view(), name="status-update"),
    path("<int:job_pk>/cv/upload/", JobInlineCVUploadView.as_view(), name="inline-cv-upload"),
    path("<int:job_pk>/notes/add/", NoteCreateView.as_view(), name="note-add"),
    path("categories/", CategoryListView.as_view(), name="category-list"),
    path("categories/new/", CategoryCreateView.as_view(), name="category-create"),
    path("categories/<int:pk>/edit/", CategoryUpdateView.as_view(), name="category-update"),
    path("categories/<int:pk>/delete/", CategoryDeleteView.as_view(), name="category-delete"),
    path("cvs/", CVListView.as_view(), name="cv-list"),
    path("cvs/new/", CVCreateView.as_view(), name="cv-create"),
    path("cvs/<int:pk>/preview/", CVPreviewView.as_view(), {"file_type": "file"}, name="cv-preview"),
    path("<int:pk>/cover-letter/preview/", JobCoverLetterPreviewView.as_view(), name="job-cover-letter-preview"),
    path("cvs/<int:pk>/edit/", CVUpdateView.as_view(), name="cv-update"),
    path("cvs/<int:pk>/delete/", CVDeleteView.as_view(), name="cv-delete"),
    path("kanban/", KanbanView.as_view(), name="kanban"),
]
