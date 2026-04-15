import os
import subprocess
from django.conf import settings
import threading
from student.models import Module


def convert_to_dash(input_path, module_id):
    """
    Convert a video file to DASH format with multiple quality representations.
    Generates manifest.mpd + DASH segments in media/videos/dash/module_<id>/.
    """
    output_dir = os.path.join(settings.MEDIA_ROOT, "videos", "dash", f"module_{module_id}")
    os.makedirs(output_dir, exist_ok=True)

    temp_output_path = os.path.join(output_dir, "manifest_tmp.mpd")
    final_output_path = os.path.join(output_dir, "manifest.mpd")
    
    # Ensure no stale temp file exists
    if os.path.exists(temp_output_path):
        try:
            os.remove(temp_output_path)
        except OSError:
            pass

    ffmpeg_binary = getattr(settings, "FFMPEG_BINARY", "ffmpeg")

    command = [
        ffmpeg_binary,
        "-y",
        "-i", input_path,
        # FORCE COMPATIBLE CODEC
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "21",
        "-c:a", "aac",
        "-b:a", "192k",
        "-g", "48",
        "-keyint_min", "48",
        "-sc_threshold", "0",
        "-map", "0:v",
        "-map", "0:v",
        "-map", "0:v",
        "-map", "0:v",
        "-map", "0:v",
        "-map", "0:a?",
        "-b:v:0", "600k", "-filter:v:0", "scale=-2:240",
        "-b:v:1", "1200k", "-filter:v:1", "scale=-2:360",
        "-b:v:2", "2500k", "-filter:v:2", "scale=-2:480",
        "-b:v:3", "5000k", "-filter:v:3", "scale=-2:720",
        "-b:v:4", "8000k", "-filter:v:4", "scale=-2:1080",
        "-use_template", "1",
        "-use_timeline", "1",
        "-init_seg_name", "init-stream$RepresentationID$.m4s",
        "-media_seg_name", "chunk-stream$RepresentationID$-$Number%05d$.m4s",
        "-adaptation_sets", "id=0,streams=v id=1,streams=a",
        "-f", "dash",
        temp_output_path
    ]

    try:
        print(f"[DASH] Starting FFmpeg transcode for module {module_id}...")
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            cwd=output_dir,
        )
        print(f"[DASH] Transcode complete for module {module_id}.")
        
        # Atomically rename to final manifest
        if os.path.exists(final_output_path):
            os.remove(final_output_path)
        os.rename(temp_output_path, final_output_path)
        
    except FileNotFoundError:
        print("[DASH] FFmpeg not found. Ensure ffmpeg is installed and on PATH.")
        return None
    except subprocess.CalledProcessError as exc:
        stderr_tail = str(exc.stderr or "").strip()
        if stderr_tail:
            stderr_tail = stderr_tail[max(0, len(stderr_tail) - 2000):]
        print(f"[DASH] FFmpeg failed for module {module_id}:\n{stderr_tail}")
        return None

    if not os.path.exists(final_output_path):
        print(f"[DASH] manifest.mpd not found after transcode for module {module_id}.")
        return None

    relative = os.path.relpath(final_output_path, settings.MEDIA_ROOT).replace("\\", "/")
    print(f"[DASH] Manifest saved: {relative}")
    return relative

_transcode_lock = threading.Lock()
ACTIVE_TRANSCODES = set()

def process_video_background(module_id):
    with _transcode_lock:
        if module_id in ACTIVE_TRANSCODES:
            print(f"[DASH] Module {module_id} is already being processed. Skipping redundant thread.")
            return
        ACTIVE_TRANSCODES.add(module_id)

    try:
        module = Module.objects.get(id=module_id)
        if not module.video_file:
            return

        input_path = module.video_file.path
        relative_manifest = convert_to_dash(input_path, module.id)

        if relative_manifest:
            module.dash_manifest = relative_manifest
            module.save(update_fields=["dash_manifest"])
            print(f"[DASH] Finished processing module {module_id}.")
    except Exception as e:
        print(f"Error processing video module {module_id}: {e}")
    finally:
        with _transcode_lock:
            ACTIVE_TRANSCODES.discard(module_id)

def trigger_dash_transcode(module_id):
    thread = threading.Thread(target=process_video_background, args=(module_id,))
    thread.daemon = True
    thread.start()
