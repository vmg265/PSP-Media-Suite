import os
import subprocess
from PIL import Image
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB
from core.config import get_resource_path

def get_ffmpeg_path():
    """Returns absolute path to ffmpeg binary (bundled or in root/PATH)."""
    binary = "ffmpeg.exe" if os.name == 'nt' else "ffmpeg"
    return get_resource_path(binary)

def get_ffprobe_path():
    """Returns absolute path to ffprobe binary."""
    binary = "ffprobe.exe" if os.name == 'nt' else "ffprobe"
    return get_resource_path(binary)

def get_startupinfo():
    """Returns subprocess startupinfo to hide CMD window on Windows."""
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return startupinfo
    return None

def crop_and_save_cover(pil_img, output_path, size=(600, 600)):
    """Crops an image into a 1:1 square and saves it as a high quality JPEG."""
    w, h = pil_img.size
    s = min(w, h)
    left = (w - s) // 2
    top = (h - s) // 2
    cropped = pil_img.crop((left, top, left + s, top + s))
    resized = cropped.resize(size, Image.Resampling.LANCZOS)
    resized.convert('RGB').save(output_path, "JPEG", quality=85)

def crop_and_save_thm(pil_img, output_path):
    """
    Crops an image to a 4:3 ratio and resizes to 160x120 for PSP XMB video thumbnails (.thm).
    """
    w, h = pil_img.size
    target_ratio = 160 / 120.0
    if w / h > target_ratio:
        target_w = int(target_ratio * h)
        left = (w - target_w) // 2
        cropped = pil_img.crop((left, 0, left + target_w, h))
    else:
        target_h = int(w / target_ratio)
        top = (h - target_h) // 2
        cropped = pil_img.crop((0, top, w, top + target_h))
    cropped.resize((160, 120), Image.Resampling.LANCZOS).convert('RGB').save(output_path, "JPEG")

def apply_mp3_tags(mp3_path, title, artist="YouTube Audio", album="PSP Media Suite", cover_path=None):
    """Writes standard ID3v2.3 tags and embedded album art onto an MP3 file."""
    audio = MP3(mp3_path, ID3=ID3)
    if audio.tags is None:
        audio.add_tags()
    else:
        audio.tags.clear()

    audio.tags.add(TIT2(encoding=3, text=title))
    audio.tags.add(TPE1(encoding=3, text=artist))
    audio.tags.add(TALB(encoding=3, text=album))

    if cover_path and os.path.exists(cover_path):
        try:
            with open(cover_path, "rb") as af:
                audio.tags.add(APIC(
                    encoding=3,
                    mime='image/jpeg',
                    type=3,
                    desc='Cover',
                    data=af.read()
                ))
        except Exception:
            pass

    audio.save(v2_version=3, v1=2)

def transcode_local_audio(input_path, output_mp3_path):
    """Converts any local audio file into a PSP-compatible 192k MP3."""
    ff_path = get_ffmpeg_path()
    cmd = [
        ff_path, "-y", "-i", input_path,
        "-vn", "-ar", "44100", "-ac", "2", "-b:a", "192k",
        output_mp3_path
    ]
    subprocess.run(cmd, startupinfo=get_startupinfo(), check=True)

def transcode_video_to_psp(input_path, output_mp4_path):
    """
    Transcodes any input video into PSP-compliant H.264 Baseline Profile 3.0 at 480x272.
    """
    ff_path = get_ffmpeg_path()
    cmd = [
        ff_path, "-y", "-i", input_path,
        "-c:v", "libx264", "-profile:v", "baseline", "-level", "3.0",
        "-pix_fmt", "yuv420p", "-vf", "scale=480:272",
        "-b:v", "768k", "-c:a", "aac", "-ac", "2", "-b:a", "128k",
        "-ar", "48000", output_mp4_path
    ]
    subprocess.run(cmd, startupinfo=get_startupinfo(), check=True)

def extract_video_frame(video_path, output_jpg_path, timestamp="00:00:01"):
    """Extracts a still video frame for use as thumbnail."""
    ff_path = get_ffmpeg_path()
    cmd = [
        ff_path, "-y", "-i", video_path,
        "-ss", timestamp, "-vframes", "1",
        output_jpg_path
    ]
    subprocess.run(cmd, startupinfo=get_startupinfo(), check=False)

def cleanup_temp_files(directory=".", task_id=None):
    """Cleans up temporary conversion artifacts and partial downloads."""
    try:
        for f in os.listdir(directory):
            if task_id:
                if task_id in f and (f.startswith("temp_raw") or f.startswith("cover")):
                    try:
                        os.remove(os.path.join(directory, f))
                    except Exception:
                        pass
            else:
                if f.startswith("temp.") or f.startswith("temp_raw.") or f in ("temp_thumb.jpg", "cover.jpg"):
                    try:
                        os.remove(os.path.join(directory, f))
                    except Exception:
                        pass
    except Exception:
        pass
