from django.contrib import admin

from jobs.models import ActivityLog, Category, JobApplication, Note, Reminder

admin.site.register(Category)
admin.site.register(JobApplication)
admin.site.register(Note)
admin.site.register(Reminder)
admin.site.register(ActivityLog)

# Register your models here.
