from celery import shared_task
import os
from django.conf import settings
from .models import Lecture
from .utils import convert_to_hls, get_video_duration

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=30, retry_kwargs={"max_retries": 3})
def process_lecture_video(self, lecture_id):
    lecture = Lecture.objects.get(id=lecture_id)

    try:
        lecture.processing_status = "processing"
        lecture.save(update_fields=["processing_status"])

        input_path = lecture.original_video.path
        output_dir = os.path.join(settings.MEDIA_ROOT, "lectures", "processed", f"lecture_{lecture.id}")

        # Convert video to HLS - returns relative path from MEDIA_ROOT
        hls_relative_path = convert_to_hls(input_path, output_dir)
        duration = get_video_duration(input_path)

        # ✅ Just store the relative path - file is already in correct location
        lecture.processed_video.name = hls_relative_path
        lecture.duration = duration
        lecture.processing_status = "completed"
        lecture.save(update_fields=["processed_video", "duration", "processing_status"])

        # Optional cleanup of original video
        # if os.path.exists(input_path):
        #     os.remove(input_path)
        #     lecture.original_video.delete(save=False)

    except Exception as e:
        lecture.processing_status = "failed"
        lecture.save(update_fields=["processing_status"])
        raise e