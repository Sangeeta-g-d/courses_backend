from celery import shared_task
import os
import tempfile
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .models import Lecture
from .utils import convert_to_hls, get_video_duration
import shutil

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=30, retry_kwargs={"max_retries": 3})
def process_lecture_video(self, lecture_id):
    lecture = Lecture.objects.get(id=lecture_id)
    
    temp_input = None
    temp_output_dir = None

    try:
        lecture.processing_status = "processing"
        lecture.save(update_fields=["processing_status"])

        # ✅ Download original video to temporary local file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_video:
            temp_input = temp_video.name
            
            # Read from storage (works with S3 or local)
            with lecture.original_video.open('rb') as source:
                shutil.copyfileobj(source, temp_video, length=1024*1024)

        # ✅ Create temp directory for HLS output
        temp_output_dir = tempfile.mkdtemp()
        
        # Convert video to HLS in temp location
        hls_output_path = convert_to_hls(temp_input, temp_output_dir)
        duration = get_video_duration(temp_input)

        # ✅ Upload HLS files to storage
        upload_hls_to_storage(lecture.id, temp_output_dir)
        
        # ✅ Set the processed_video path
        lecture.processed_video.name = f"lectures/processed/lecture_{lecture.id}/index.m3u8"
        lecture.duration = duration
        lecture.processing_status = "completed"
        lecture.save(update_fields=["processed_video", "duration", "processing_status"])

    except Exception as e:
        lecture.processing_status = "failed"
        lecture.save(update_fields=["processing_status"])
        raise e
        
    finally:
        # ✅ Cleanup temp files
        if temp_input and os.path.exists(temp_input):
            os.remove(temp_input)
        
        if temp_output_dir and os.path.exists(temp_output_dir):
            import shutil
            shutil.rmtree(temp_output_dir, ignore_errors=True)


def upload_hls_to_storage(lecture_id, local_dir):
    """
    Upload all HLS files (m3u8 + segments) to Django storage.
    Works with both local storage and S3.
    """
    base_path = f"lectures/processed/lecture_{lecture_id}"
    
    for filename in os.listdir(local_dir):
        local_file_path = os.path.join(local_dir, filename)
        storage_path = f"{base_path}/{filename}"
        
        with open(local_file_path, 'rb') as f:
            default_storage.save(storage_path, ContentFile(f.read()))