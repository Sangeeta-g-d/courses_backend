import os
import json
import shutil
import subprocess
import platform
from django.conf import settings
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile


# =========================================================
# FFmpeg / FFprobe PATH RESOLUTION (PRODUCTION SAFE)
# =========================================================

def find_ffmpeg_binary_windows(name):
    """
    Find ffmpeg / ffprobe on Windows systems.
    """
    binary = shutil.which(name)
    if binary:
        return binary

    common_paths = [
        r"C:\ffmpeg\bin",
        r"C:\ffmpeg-8.1-essentials_build\bin",
        r"C:\Program Files\ffmpeg\bin",
        r"C:\Program Files (x86)\ffmpeg\bin",
    ]

    for path in common_paths:
        full_path = os.path.join(path, f"{name}.exe")
        if os.path.exists(full_path):
            return full_path

    return name  # Let it fail with helpful error


# Detect OS and assign paths
if platform.system() == "Windows":
    FFMPEG_PATH = find_ffmpeg_binary_windows("ffmpeg")
    FFPROBE_PATH = find_ffmpeg_binary_windows("ffprobe")
else:
    # Linux / AWS / VPS (BEST PRACTICE)
    FFMPEG_PATH = "/usr/bin/ffmpeg"
    FFPROBE_PATH = "/usr/bin/ffprobe"


# Safety check (fail fast on server)
if not os.path.exists(FFMPEG_PATH):
    raise RuntimeError(f"FFmpeg not found at {FFMPEG_PATH}")

if not os.path.exists(FFPROBE_PATH):
    raise RuntimeError(f"FFprobe not found at {FFPROBE_PATH}")


# =========================================================
# VIDEO DURATION
# =========================================================

def get_video_duration(video_path):
    """
    Get video duration in seconds using ffprobe.
    """
    command = [
        FFPROBE_PATH,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        video_path,
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
        return round(duration, 2)

    except subprocess.CalledProcessError as e:
        raise Exception(f"FFprobe error: {e.stderr}")

    except (KeyError, ValueError, json.JSONDecodeError):
        raise Exception("Failed to parse video duration")


# =========================================================
# HLS CONVERSION
# =========================================================

def convert_to_hls(input_path, output_dir):
    """
    Convert video to HLS (.m3u8) format.
    Returns relative path to the master playlist.
    """
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "index.m3u8")

    command = [
        FFMPEG_PATH,
        "-y",
        "-i", input_path,
        "-c:v", "libx264",
        "-preset", "ultrafast",   # 🔥 BIG SPEED GAIN
        "-crf", "30",
        "-threads", "1",          # prevent CPU hog
        "-hls_time", "6",
        "-hls_playlist_type", "vod",
        "-hls_segment_filename",
        os.path.join(output_dir, "segment_%03d.ts"),
        "-f", "hls",
        output_path,
    ]


    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=1800,  # 10 minutes
        )

    except subprocess.TimeoutExpired:
        raise Exception("FFmpeg conversion timed out")

    except subprocess.CalledProcessError as e:
        raise Exception(f"FFmpeg conversion failed: {e.stderr}")

    return os.path.relpath(output_path, settings.MEDIA_ROOT)


# =========================================================
# DURATION FORMATTER
# =========================================================

def format_duration(seconds):
    """
    Convert seconds to readable format.
    """
    if not seconds:
        return "0:00"

    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours:
        return f"{hours}h {minutes}m {secs}s"
    return f"{minutes}m {secs}s"

# =========================================================
# NO-CACHE DECORATOR FOR ADMIN PAGES
# =========================================================

def no_cache(view_func):
    """
    Decorator to add no-cache headers to responses.
    This prevents browser from caching pages, ensuring back button
    doesn't return to sensitive admin pages after logout.
    """
    def wrapper(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        # Add no-cache headers to prevent caching
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    return wrapper


# =========================================================
# IMAGE COMPRESSION
# =========================================================

def compress_image(image_file, quality=85, max_size=(1920, 1080)):
    """
    Compress an image file to reduce size.
    - Converts to JPEG format
    - Resizes if larger than max_size
    - Applies quality compression

    Args:
        image_file: Django's InMemoryUploadedFile or file-like object
        quality: JPEG quality (0-100, default 85)
        max_size: Max (width, height) tuple, resizes if exceeded

    Returns:
        Compressed ContentFile with same name
    """
    img = Image.open(image_file)

    # Convert to RGB if necessary (for PNG, etc.)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    # Resize if too large
    if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
        img.thumbnail(max_size, Image.Resampling.LANCZOS)

    # Compress and save to BytesIO
    output = BytesIO()
    img.save(output, format='JPEG', quality=quality, optimize=True)
    output.seek(0)

    # Create new ContentFile with original name
    compressed_file = ContentFile(output.getvalue(), name=image_file.name)

    return compressed_file