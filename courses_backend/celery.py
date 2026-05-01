import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "courses_backend.settings")

app = Celery("courses_backend")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Celery Beat Schedule for periodic tasks
app.conf.beat_schedule = {
    "cleanup-inactive-meetings-daily": {
        "task": "admin_part.tasks.cleanup_inactive_meetings",
        "schedule": crontab(hour=1, minute=0),  # Runs daily at 1:00 AM IST
    },
}
