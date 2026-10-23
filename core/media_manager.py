import os
import sys
import datetime
import subprocess
from io import BytesIO
from PIL import Image
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, APIC
from core.device import get_music_dir, get_video_dir, get_playlist_dir

AUDIO_EXTS = (".mp3", ".ogg", ".opus", ".m4a", ".wav")
VIDEO_EXTS = (".mp4", ".avi", ".mkv", ".mov")

_COVER_CACHE = {}

def list_media_files(folder, exts):
    """Returns a list of tuples: (filename, formatted_size_str)."""
    return [(f['name'], f['size_str']) for f in get_detailed_media_files(folder, exts)]

def get_detailed_media_files(folder, exts):
    """
    Returns a list of dicts with full metadata for each matching file:
    [{'name', 'path', 'size_bytes', 'size_str', 'mtime', 'date_str'}, ...]
    """
    results = []
    if not os.path.exists(folder):
        return results

    try:
        for f in sorted(os.listdir(folder)):
            if f.lower().endswith(exts):
                fp = os.path.join(folder, f)
                try:
                    st = os.stat(fp)
                    size_kb = st.st_size / 1024
                    if size_kb > 1024:
                        size_str = f"{size_kb / 1024:.1f} MB"
                    else:
                        size_str = f"{size_kb:.0f} KB"
                    date_str = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
                    results.append({
                        'name': f,
                        'path': fp,
                        'size_bytes': st.st_size,
                        'size_str': size_str,
                        'mtime': st.st_mtime,
                        'date_str': date_str
                    })
                except Exception:
                    pass
    except Exception:
        pass
    return results

def get_file_cover(filepath, media_type):
    """
    Extracts cover art from an MP3's ID3 APIC tag, or reads the companion .thm for video files.
    Returns a PIL.Image or None.
    """
    if not os.path.exists(filepath):
        return None

    try:
        if media_type == 'audio':
            tags = None
            try:
                audio = MP3(filepath, ID3=ID3)
                tags = audio.tags
            except Exception:
                try:
                    tags = ID3(filepath)
                except Exception:
                    tags = None
            if tags:
                for tag in tags.values():
                    if isinstance(tag, APIC):
                        img = Image.open(BytesIO(tag.data))
                        img.load()
                        return img
        elif media_type == 'video':
            thm_path = os.path.splitext(filepath)[0] + ".thm"
            if os.path.exists(thm_path):
                img = Image.open(thm_path)
                img.load()
                return img
            # Fallback: Extract video frame thumbnail if no .thm exists
            try:
                from core.transcoder import get_ffmpeg_path
                ff = get_ffmpeg_path()
                if os.path.exists(ff):
                    cmd = [ff, '-ss', '00:00:01', '-i', filepath, '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-']
                    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    out, _ = p.communicate(timeout=4)
                    if out:
                        img = Image.open(BytesIO(out))
                        img.load()
                        return img
            except Exception:
                pass
    except Exception:
        pass
    return None

def get_cached_cover(filepath, media_type, target_size=(100, 100)):
    """
    Cached cover art retriever returning a resized PIL.Image.
    Keyed by filepath + modification time + target size.
    """
    if not os.path.exists(filepath):
        return None
    try:
        mtime = os.path.getmtime(filepath)
    except Exception:
        mtime = 0

    cache_key = (filepath, mtime, target_size)
    if cache_key in _COVER_CACHE:
        return _COVER_CACHE[cache_key]

    img = get_file_cover(filepath, media_type)
    if img:
        try:
            img = img.resize(target_size, Image.Resampling.LANCZOS)
        except Exception:
            pass
    _COVER_CACHE[cache_key] = img
    return img

def sort_media_files(files, sort_key="name_asc"):
    """
    Sorts a list of file metadata dicts by specified key.
    sort_key options: 'name_asc', 'name_desc', 'date_desc', 'date_asc', 'size_desc', 'size_asc'.
    """
    if sort_key == "name_asc":
        return sorted(files, key=lambda x: x['name'].lower())
    elif sort_key == "name_desc":
        return sorted(files, key=lambda x: x['name'].lower(), reverse=True)
    elif sort_key == "date_desc":
        return sorted(files, key=lambda x: x['mtime'], reverse=True)
    elif sort_key == "date_asc":
        return sorted(files, key=lambda x: x['mtime'])
    elif sort_key == "size_desc":
        return sorted(files, key=lambda x: x['size_bytes'], reverse=True)
    elif sort_key == "size_asc":
        return sorted(files, key=lambda x: x['size_bytes'])
    return files

def rename_media_file(folder, drive, media_type, old_name, new_base):
    """
    Renames a media file on the PSP.
    - If video: renames the companion .thm thumbnail file if it exists.
    - If audio: updates the ID3 title tag and updates references in all .m3u8 playlists.
    """
    ext = os.path.splitext(old_name)[1]
    old_base = os.path.splitext(old_name)[0]
    new_name = new_base.strip() + ext

    old_path = os.path.join(folder, old_name)
    new_path = os.path.join(folder, new_name)
    os.rename(old_path, new_path)

    if media_type == 'video':
        old_thm = os.path.join(folder, old_base + ".thm")
        new_thm = os.path.join(folder, new_base.strip() + ".thm")
        if os.path.exists(old_thm):
            try:
                os.rename(old_thm, new_thm)
            except Exception:
                pass

        # Update references across all video .m3u8 playlists on the PSP
        pl_dir = get_playlist_dir(drive, "video")
        if os.path.exists(pl_dir):
            for pl_file in os.listdir(pl_dir):
                if pl_file.lower().endswith(".m3u8"):
                    pl_path = os.path.join(pl_dir, pl_file)
                    try:
                        with open(pl_path, "r", encoding="utf-8") as f:
                            lines = f.readlines()
                        updated = False
                        for i in range(len(lines)):
                            if lines[i].strip().lower() == f"\\video\\{old_name}".lower():
                                lines[i] = f"\\VIDEO\\{new_name}\n"
                                updated = True
                        if updated:
                            with open(pl_path, "w", encoding="utf-8") as f:
                                f.writelines(lines)
                    except Exception:
                        pass

    elif media_type == 'audio':
        if ext.lower() == '.mp3':
            try:
                audio = MP3(new_path, ID3=ID3)
                if audio.tags is None:
                    audio.add_tags()
                audio.tags.add(TIT2(encoding=3, text=new_base.strip()))
                audio.save(v2_version=3, v1=2)
            except Exception:
                pass

        # Update references across all .m3u8 playlists on the PSP
        pl_dir = get_playlist_dir(drive, "audio")
        if os.path.exists(pl_dir):
            for pl_file in os.listdir(pl_dir):
                if pl_file.lower().endswith(".m3u8"):
                    pl_path = os.path.join(pl_dir, pl_file)
                    try:
                        with open(pl_path, "r", encoding="utf-8") as f:
                            lines = f.readlines()
                        updated = False
                        for i in range(len(lines)):
                            if lines[i].strip().lower() == f"\\music\\{old_name}".lower():
                                lines[i] = f"\\MUSIC\\{new_name}\n"
                                updated = True
                        if updated:
                            with open(pl_path, "w", encoding="utf-8") as f:
                                f.writelines(lines)
                    except Exception:
                        pass
    return new_name

def delete_media_files(folder, media_type, file_list):
    """Deletes selected media files and their corresponding .thm files if video."""
    for fname in file_list:
        file_path = os.path.join(folder, fname)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            if media_type == 'video':
                thm_path = os.path.join(folder, os.path.splitext(fname)[0] + ".thm")
                if os.path.exists(thm_path):
                    try:
                        os.remove(thm_path)
                    except Exception:
                        pass
        except Exception as e:
            raise e

def open_system_folder(folder):
    """Opens a directory in the host OS default file manager."""
    if sys.platform == "win32":
        os.startfile(folder)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", folder])
    else:
        subprocess.Popen(["xdg-open", folder])

# ─── PLAYLIST OPERATIONS ──────────────────────────────────────────────────────

def get_playlist_file_path(pl_dir, name):
    return os.path.join(pl_dir, name + ".m3u8")

def list_playlists(pl_dir):
    """Returns a list of playlist names (without .m3u8 extension)."""
    if not os.path.exists(pl_dir):
        return []
    playlists = []
    try:
        for f in sorted(os.listdir(pl_dir)):
            if f.lower().endswith(".m3u8"):
                playlists.append(os.path.splitext(f)[0])
    except Exception:
        pass
    return playlists

def read_playlist(pl_dir, name):
    """Reads a playlist file and returns list of non-empty track lines."""
    path = get_playlist_file_path(pl_dir, name)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip()]

def write_playlist(pl_dir, name, lines):
    """Writes track lines to a playlist file."""
    os.makedirs(pl_dir, exist_ok=True)
    with open(get_playlist_file_path(pl_dir, name), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def song_display_name(raw_line):
    """Extracts human-readable filename from a playlist line with backslashes."""
    return os.path.basename(raw_line.replace("\\", "/"))

media_display_name = song_display_name

def create_playlist(pl_dir, name):
    """Creates a new empty playlist file."""
    path = get_playlist_file_path(pl_dir, name)
    if os.path.exists(path):
        return False, "Playlist already exists"
    write_playlist(pl_dir, name, [])
    return True, None

def rename_playlist(pl_dir, old_name, new_name):
    """Renames a playlist .m3u8 file."""
    old_path = get_playlist_file_path(pl_dir, old_name)
    new_path = get_playlist_file_path(pl_dir, new_name)
    os.rename(old_path, new_path)

def delete_playlist(pl_dir, name):
    """Deletes a playlist .m3u8 file."""
    path = get_playlist_file_path(pl_dir, name)
    if os.path.exists(path):
        os.remove(path)

def list_available_mp3s(music_dir):
    """Returns a list of all .mp3 files available in the MUSIC directory."""
    if not os.path.exists(music_dir):
        return []
    try:
        return [f for f in sorted(os.listdir(music_dir)) if f.lower().endswith(".mp3")]
    except Exception:
        return []

def list_available_videos(video_dir):
    """Returns a list of all video files available in the VIDEO directory."""
    if not os.path.exists(video_dir):
        return []
    try:
        return [f for f in sorted(os.listdir(video_dir)) if f.lower().endswith(VIDEO_EXTS)]
    except Exception:
        return []

def list_available_media(folder, media_type):
    """Returns a list of media files in folder matching the media_type ('audio' or 'video')."""
    if media_type == "audio":
        return list_available_mp3s(folder)
    else:
        return list_available_videos(folder)

def update_media_cover(filepath, media_type, pil_image):
    """
    Updates or embeds a new cover thumbnail for a music or video file on the PSP.
    - Audio (.mp3): encodes 600x600 JPEG and injects ID3 APIC frame.
    - Video: saves 160x120 JPEG companion .thm file next to video.
    Clears cached thumbnail entries.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    if media_type == 'audio':
        cover_resized = pil_image.resize((600, 600), Image.Resampling.LANCZOS).convert('RGB')
        buf = BytesIO()
        cover_resized.save(buf, "JPEG", quality=85)
        jpeg_data = buf.getvalue()

        apic_frame = APIC(
            encoding=3,
            mime='image/jpeg',
            type=3,
            desc='Cover',
            data=jpeg_data
        )

        try:
            audio = MP3(filepath, ID3=ID3)
            if audio.tags is None:
                audio.add_tags()
            else:
                audio.tags.delall('APIC')
            audio.tags.add(apic_frame)
            audio.save(v2_version=3, v1=2)
        except Exception:
            try:
                id3 = ID3(filepath)
            except Exception:
                id3 = ID3()
            id3.delall('APIC')
            id3.add(apic_frame)
            id3.save(filepath, v2_version=3, v1=2)

    elif media_type == 'video':
        thm_path = os.path.splitext(filepath)[0] + ".thm"
        cover_resized = pil_image.resize((160, 120), Image.Resampling.LANCZOS).convert('RGB')
        cover_resized.save(thm_path, "JPEG", quality=90)

    # Invalidate cache for this file
    keys_to_del = [k for k in _COVER_CACHE if k[0] == filepath]
    for k in keys_to_del:
        del _COVER_CACHE[k]
