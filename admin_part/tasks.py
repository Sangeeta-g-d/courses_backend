from celery import shared_task
import os
from django.conf import settings
from .models import Lecture
from .utils import convert_to_hls, get_video_duration


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=30, retry_kwargs={"max_retries": 3})
def process_lecture_video(self, lecture_id):
    lecture = Lecture.objects.get(id=lecture_id)

    try:
        lecture.status = "processing"
        lecture.save(update_fields=["status"])

        input_path = lecture.video.path
        output_dir = os.path.join(
            settings.MEDIA_ROOT, "lectures", f"lecture_{lecture.id}"
        )

        hls_path = convert_to_hls(input_path, output_dir)
        duration = get_video_duration(input_path)

        lecture.hls_path = hls_path
        lecture.duration = duration
        lecture.status = "ready"
        lecture.save()

        # cleanup original video
        if os.path.exists(input_path):
            os.remove(input_path)

    except Exception:
        lecture.status = "failed"
        lecture.save(update_fields=["status"])
        raise
