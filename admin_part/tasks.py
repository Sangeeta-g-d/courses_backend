from celery import shared_task
import os
from django.conf import settings
from django.core.files import File
from .models import Lecture
from .utils import convert_to_hls, get_video_duration

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=30, retry_kwargs={"max_retries": 3})
def process_lecture_video(self, lecture_id):
    lecture = Lecture.objects.get(id=lecture_id)

    try:
        lecture.processing_status = "processing"
        lecture.save(update_fields=["processing_status"])

        input_path = lecture.original_video.path
        output_dir = os.path.join(settings.MEDIA_ROOT, "lectures", f"lecture_{lecture.id}")

        hls_path = convert_to_hls(input_path, output_dir)
        duration = get_video_duration(input_path)

        # Assign processed video using Django File object
        full_hls_path = os.path.join(settings.MEDIA_ROOT, hls_path)
        with open(full_hls_path, "rb") as f:
            django_file = File(f)
            lecture.processed_video.save(f"lecture_{lecture.id}/index.m3u8", django_file, save=False)

        lecture.duration = duration
        lecture.processing_status = "completed"
        lecture.save(update_fields=["processed_video", "duration", "processing_status"])

        # Optional cleanup of original video
        # os.remove(input_path)

    except Exception as e:
        lecture.processing_status = "failed"
        lecture.save(update_fields=["processing_status"])
        raise e
