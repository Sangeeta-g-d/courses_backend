from celery import shared_task
import os
from django.conf import settings
from .models import Lecture
from .utils import convert_to_hls, get_video_duration


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=30, retry_kwargs={"max_retries": 3})
def process_lecture_video(self, lecture_id):
    lecture = Lecture.objects.get(id=lecture_id)

    try:
        # ✅ Mark as processing
        lecture.processing_status = "processing"
        lecture.save(update_fields=["processing_status"])

        # ✅ Correct input path
        input_path = lecture.original_video.path

        # Output HLS directory
        output_dir = os.path.join(
            settings.MEDIA_ROOT, "lectures", f"lecture_{lecture.id}"
        )

        # Convert video → HLS
        hls_relative_path = convert_to_hls(input_path, output_dir)

        # Get duration
        duration = get_video_duration(input_path)

        # ✅ Save results
        lecture.processed_video.name = hls_relative_path
        lecture.duration = duration
        lecture.processing_status = "completed"

        lecture.save(update_fields=[
            "processed_video",
            "duration",
            "processing_status"
        ])

        # ✅ Cleanup original upload
        if os.path.exists(input_path):
            os.remove(input_path)

    except Exception as e:
        lecture.processing_status = "failed"
        lecture.save(update_fields=["processing_status"])
        raise
