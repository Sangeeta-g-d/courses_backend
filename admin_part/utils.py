import os
import json
import subprocess
import shutil
from django.conf import settings


def find_ffmpeg_binary(name):
    """
    Try to find ffmpeg/ffprobe binary.
    First checks if it's in PATH, then checks common Windows locations.
    """
    # Try to find in PATH
    binary = shutil.which(name)
    if binary:
        return binary
    
    # Common Windows installation paths
    common_paths = [
        r"C:\ffmpeg\bin",
        r"C:\ffmpeg-8.0-essentials_build\bin",
        r"C:\Program Files\ffmpeg\bin",
        r"C:\Program Files (x86)\ffmpeg\bin",
    ]
    
    for path in common_paths:
        full_path = os.path.join(path, f"{name}.exe")
        if os.path.exists(full_path):
            return full_path
    
    # If not found, return the name and let it fail with helpful error
    return name


# Get FFmpeg paths
FFMPEG_PATH = find_ffmpeg_binary("ffmpeg")
FFPROBE_PATH = find_ffmpeg_binary("ffprobe")


def get_video_duration(video_path):
    """Get video duration in seconds using ffprobe."""
    command = [
        FFPROBE_PATH,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        video_path
    ]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        duration = float(data['format']['duration'])
        return round(duration, 2)
    except FileNotFoundError:
        raise Exception(
            f"FFprobe not found at: {FFPROBE_PATH}\n"
            "Please ensure FFmpeg is installed and in your system PATH.\n"
            "Installation guide: https://www.gyan.dev/ffmpeg/builds/"
        )
    except subprocess.CalledProcessError as e:
        raise Exception(f"FFprobe error: {e.stderr}")
    except (KeyError, ValueError) as e:
        raise Exception(f"Error parsing video duration: {str(e)}")


def convert_to_hls(input_path, output_dir):
    """
    Convert uploaded video to HLS (.m3u8) format using ffmpeg.
    Returns relative path to the HLS master playlist.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "index.m3u8")

    # FFmpeg command for HLS conversion with better quality settings
    command = [
        FFMPEG_PATH,
        "-i", input_path,
        "-codec:v", "libx264",  # Video codec
        "-codec:a", "aac",      # Audio codec
        "-preset", "medium",    # Encoding speed/quality tradeoff
        "-crf", "23",           # Quality (lower = better, 18-28 is good range)
        "-sc_threshold", "0",   # Disable scene change detection
        "-g", "48",             # GOP size (keyframe interval)
        "-keyint_min", "48",
        "-hls_time", "10",      # Segment duration in seconds
        "-hls_playlist_type", "vod",
        "-hls_segment_filename", os.path.join(output_dir, "segment_%03d.ts"),
        "-start_number", "0",
        "-hls_list_size", "0",
        "-f", "hls",
        output_path,
    ]

    try:
        result = subprocess.run(
            command, 
            check=True, 
            capture_output=True, 
            text=True,
            timeout=300  # 5 minute timeout
        )
    except FileNotFoundError:
        raise Exception(
            f"FFmpeg not found at: {FFMPEG_PATH}\n"
            "Please ensure FFmpeg is installed and in your system PATH.\n"
            "Installation guide: https://www.gyan.dev/ffmpeg/builds/"
        )
    except subprocess.TimeoutExpired:
        raise Exception("FFmpeg conversion timed out (took longer than 5 minutes)")
    except subprocess.CalledProcessError as e:
        raise Exception(f"FFmpeg conversion failed: {e.stderr}")

    # Return relative path (e.g. for saving to DB)
    rel_path = os.path.relpath(output_path, settings.MEDIA_ROOT)
    return rel_path



# Add this to your utils.py file

def format_duration(seconds):
    """Convert seconds to HH:MM:SS format"""
    if not seconds:
        return "0:00"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    return f"{minutes}m {secs}s"
