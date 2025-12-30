import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "courses_backend.settings")

app = Celery("courses_backend")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
