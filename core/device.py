import os
import shutil
import psutil

def _is_psp_folder(path, is_removable_media=False):
    """
    Checks if a directory appears to be a PSP drive / volume.
    - If is_removable_media is True (e.g. ChromeOS /mnt/chromeos/removable/*),
      the user explicitly plugged in and shared this USB drive, so even an empty
      or freshly formatted drive qualifies.
    - Otherwise, looks case-insensitively for PSP directory markers:
      PSP, MUSIC, VIDEO, ISO, MP_ROOT, PICTURE, SEPLUGINS, ROMS, RETROSHELL,
      or having 'PSP' in the volume/directory name.
    """
    if not os.path.isdir(path):
        return False

    # Drives explicitly shared from ChromeOS removable storage are always candidates
    if is_removable_media:
        return True

    base_name = os.path.basename(path).upper()
    if "PSP" in base_name:
        return True

    try:
        entries = {e.upper() for e in os.listdir(path)}
        if "PSP" in entries:
            return True
        if "MUSIC" in entries and "VIDEO" in entries:
            return True
        if bool(entries & {"ISO", "MP_ROOT", "SEPLUGINS", "RETROSHELL", "ROMS"}):
            return True
    except Exception:
        pass

    return False

def scan_psp_drives():
    """
    Scans system partitions and common removable storage locations for PSP drives
    (including multi-LUN devices like PSP Go with both Internal Storage and Memory Stick M2).
    Returns (drives_dict, display_names_list).
    """
    candidate_paths = []
    seen_paths = set()

    def add_candidate(path, is_removable_media=False):
        try:
            real_p = os.path.realpath(path)
            if real_p in seen_paths or not os.path.isdir(path):
                return
            if _is_psp_folder(path, is_removable_media=is_removable_media):
                seen_paths.add(real_p)
                candidate_paths.append((path, is_removable_media))
        except Exception:
            pass

    # 1. ChromeOS Removable & External Mounts (seneschal 9p shares)
    for cros_base in ["/mnt/chromeos/removable", "/mnt/external"]:
        if os.path.exists(cros_base):
            try:
                for item in sorted(os.listdir(cros_base)):
                    p = os.path.join(cros_base, item)
                    if os.path.isdir(p):
                        add_candidate(p, is_removable_media=True)
            except Exception:
                pass

    # 2. Linux Media Mounts (/media/*, /run/media/*, and nested user directories)
    for media_base in ["/media", "/run/media"]:
        if os.path.exists(media_base):
            try:
                for item in sorted(os.listdir(media_base)):
                    sub = os.path.join(media_base, item)
                    if os.path.isdir(sub):
                        add_candidate(sub, is_removable_media=False)
                        try:
                            for nested in sorted(os.listdir(sub)):
                                nested_p = os.path.join(sub, nested)
                                if os.path.isdir(nested_p):
                                    add_candidate(nested_p, is_removable_media=False)
                        except Exception:
                            pass
            except Exception:
                pass

    # 3. macOS Mounts (/Volumes/*)
    if os.path.exists("/Volumes"):
        try:
            for item in sorted(os.listdir("/Volumes")):
                p = os.path.join("/Volumes", item)
                if os.path.isdir(p) and not item.startswith("."):
                    add_candidate(p, is_removable_media=False)
        except Exception:
            pass

    # 4. Mounted partitions via psutil (Windows drive letters & Linux mountpoints)
    system_skips = {
        "/", "/dev", "/proc", "/sys", "/etc", "/var", "/tmp", "/boot",
        "/usr", "/run", "/opt", "/dev/shm", "/run/lock", "/sys/fs/cgroup",
        "/mnt/chromeos", "/mnt/chromeos/fonts", "/mnt/chromeos/MyFiles"
    }
    try:
        for part in psutil.disk_partitions(all=True):
            mp = part.mountpoint
            if mp in system_skips or mp.startswith(("/proc", "/sys", "/dev")):
                continue
            add_candidate(mp, is_removable_media=False)
    except Exception:
        pass

    # Pre-gather capacities to detect multi-volume PSP Go scenarios
    drives = {}
    found = []
    drive_infos = []

    for path, is_removable in candidate_paths:
        clean_p = path.rstrip("/\\")
        base_name = os.path.basename(clean_p) or clean_p
        total_gb = 0.0
        free_gb = 0.0
        try:
            total, used, free = shutil.disk_usage(path)
            total_gb = total / (1024 ** 3)
            free_gb = free / (1024 ** 3)
        except Exception:
            pass
        drive_infos.append({
            "path": path,
            "name": base_name,
            "total_gb": total_gb,
            "free_gb": free_gb,
            "is_removable": is_removable
        })

    # Detect if multiple drives exist (e.g. PSP Go dual internal + M2 card)
    has_multiple = len(drive_infos) > 1

    for info in drive_infos:
        path = info["path"]
        name = info["name"]
        total_gb = info["total_gb"]
        free_gb = info["free_gb"]

        size_text = f" ({total_gb:.1f} GB, {free_gb:.1f} GB free)" if total_gb > 0 else ""

        tag = ""
        if has_multiple:
            lower_name = name.lower()
            if "internal" in lower_name or "ef0" in lower_name:
                tag = " [Internal]"
            elif "m2" in lower_name or "ms0" in lower_name or "memory" in lower_name:
                tag = " [Memory Stick]"
            elif 14.2 <= total_gb <= 15.2 and any(other["total_gb"] < 14.0 or other["total_gb"] > 16.0 for other in drive_infos if other != info):
                tag = " [PSP Go Internal]"
            elif any(14.2 <= other["total_gb"] <= 15.2 for other in drive_infos if other != info) and (total_gb < 14.0 or total_gb > 16.0):
                tag = " [M2 Memory Stick]"

        label = f"{name}{size_text}{tag}"

        if label in drives:
            idx = 2
            while f"{name} #{idx}{size_text}{tag}" in drives:
                idx += 1
            label = f"{name} #{idx}{size_text}{tag}"

        drives[label] = path
        found.append(label)

    return drives, found

def get_music_dir(drive_path):
    """Returns path to the PSP MUSIC directory (case-insensitive lookup)."""
    if not drive_path:
        return ""
    for candidate in ["MUSIC", "music", "Music"]:
        p = os.path.join(drive_path, candidate)
        if os.path.isdir(p):
            return p
    return os.path.join(drive_path, "MUSIC")

def get_video_dir(drive_path):
    """Returns path to the PSP VIDEO directory (case-insensitive lookup)."""
    if not drive_path:
        return ""
    for candidate in ["VIDEO", "video", "Video"]:
        p = os.path.join(drive_path, candidate)
        if os.path.isdir(p):
            return p
    return os.path.join(drive_path, "VIDEO")

def get_playlist_dir(drive_path, media_type="audio"):
    """Returns path to the PSP PLAYLIST directory for music or video."""
    if not drive_path:
        return ""
    sub = "MUSIC" if media_type == "audio" else "VIDEO"
    psp_base = "PSP"
    for candidate in ["PSP", "psp", "Psp"]:
        if os.path.isdir(os.path.join(drive_path, candidate)):
            psp_base = candidate
            break
    return os.path.join(drive_path, psp_base, "PLAYLIST", sub)

def ensure_psp_dirs(drive_path):
    """Ensures that standard PSP media directories exist."""
    if not drive_path or not os.path.isdir(drive_path):
        return
    try:
        os.makedirs(get_music_dir(drive_path), exist_ok=True)
        os.makedirs(get_video_dir(drive_path), exist_ok=True)
        os.makedirs(get_playlist_dir(drive_path, "audio"), exist_ok=True)
        os.makedirs(get_playlist_dir(drive_path, "video"), exist_ok=True)
    except Exception:
        pass
