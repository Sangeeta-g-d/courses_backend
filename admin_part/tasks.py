from celery import shared_task
import os
import tempfile
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .models import Lecture
from .utils import convert_to_hls, get_video_duration
import shutil
from datetime import timedelta
from django.utils import timezone
from zoneinfo import ZoneInfo
import datetime

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=30, retry_kwargs={"max_retries": 3})
def process_lecture_video(self, lecture_id):
    lecture = Lecture.objects.get(id=lecture_id)

    temp_input = None
    temp_output_dir = None

    try:
        lecture.processing_status = "processing"
        lecture.save(update_fields=["processing_status"])

        # ==================================================
        # STEP 1: Download original video (LOCAL or S3)
        # ==================================================
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            temp_input = tmp.name

            if lecture.original_video_file:
                # LOCAL FILE
                with lecture.original_video_file.open("rb") as f:
                    shutil.copyfileobj(f, tmp, length=1024 * 1024)

            elif lecture.original_video_key:
                # S3 FILE
                with default_storage.open(lecture.original_video_key, "rb") as f:
                    shutil.copyfileobj(f, tmp, length=1024 * 1024)

            else:
                raise Exception("No original video source found")

        # ==================================================
        # STEP 2: Convert to HLS
        # ==================================================
        temp_output_dir = tempfile.mkdtemp()
        convert_to_hls(temp_input, temp_output_dir)
        duration = get_video_duration(temp_input)

        # ==================================================
        # STEP 3: Upload HLS to storage (local or S3)
        # ==================================================
        upload_hls_to_storage(lecture.id, temp_output_dir)

        lecture.processed_video.name = f"lectures/processed/lecture_{lecture.id}/index.m3u8"
        lecture.duration = duration
        lecture.processing_status = "completed"
        lecture.save(update_fields=["processed_video", "duration", "processing_status"])

    except Exception:
        lecture.processing_status = "failed"
        lecture.save(update_fields=["processing_status"])
        raise

    finally:
        if temp_input and os.path.exists(temp_input):
            os.remove(temp_input)
        if temp_output_dir and os.path.exists(temp_output_dir):
            shutil.rmtree(temp_output_dir, ignore_errors=True)



def upload_hls_to_storage(lecture_id, local_dir):
    """
    Upload all HLS files (m3u8 + .ts segments)
    Works with BOTH local filesystem and S3
    """
    base_path = f"lectures/processed/lecture_{lecture_id}"

    for filename in os.listdir(local_dir):
        local_file_path = os.path.join(local_dir, filename)
        storage_path = f"{base_path}/{filename}"

        with open(local_file_path, "rb") as f:
            default_storage.save(storage_path, ContentFile(f.read()))


@shared_task
def cleanup_inactive_meetings():
    """
    Delete LiveSession and related Post records where the session
    ended more than 60 minutes ago (i.e., is_active = False).
    Runs once daily via Celery beat schedule.
    """
    from admin_part.models import LiveSession, Post
    
    ist = ZoneInfo("Asia/Kolkata")
    now_ist = timezone.now().astimezone(ist)
    
    # Calculate the cutoff time (60 minutes ago)
    cutoff_time = now_ist - timedelta(minutes=60)
    
    # Find sessions where session datetime is older than cutoff
    inactive_sessions = []
    
    for session in LiveSession.objects.all():
        session_datetime = datetime.combine(session.session_date, session.session_time)
        session_datetime = ist.localize(session_datetime)
        
        if session_datetime < cutoff_time:
            inactive_sessions.append(session)
    
    deleted_sessions = 0
    deleted_posts = 0
    
    for session in inactive_sessions:
        # Delete related posts first
        posts_deleted = Post.objects.filter(session=session).delete()[0]
        deleted_posts += posts_deleted
        
        # Delete the session
        session.delete()
        deleted_sessions += 1
    
    return {
        "deleted_sessions": deleted_sessions,
        "deleted_posts": deleted_posts,
        "cleanup_time": now_ist.isoformat()
    }
