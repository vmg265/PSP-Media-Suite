import os
import psutil

def scan_psp_drives():
    """
    Scans system partitions and common removable storage locations for PSP drives
    (identified by having a top-level 'PSP' directory).
    Returns (drives_dict, display_names_list).
    """
    drives = {}
    found = []

    # 1. Check all mounted partitions
    for part in psutil.disk_partitions(all=True):
        try:
            psp_dir = os.path.join(part.mountpoint, "PSP")
            if os.path.exists(psp_dir):
                size_gb = psutil.disk_usage(part.mountpoint).total / (1024 ** 3)
                label = os.path.basename(part.mountpoint) or part.mountpoint
                name = f"{label} ({size_gb:.1f} GB)"
                drives[name] = part.mountpoint
                found.append(name)
        except Exception:
            continue

    # 2. Check common Linux and ChromeOS external mount directories
    if os.name != 'nt':
        for base in ["/media", "/run/media", "/mnt/chromeos/removable"]:
            if os.path.exists(base):
                try:
                    for u in os.listdir(base):
                        p = os.path.join(base, u)
                        if os.path.isdir(p) and os.path.exists(os.path.join(p, "PSP")):
                            n = f"External ({u})"
                            drives[n] = p
                            found.append(n)
                except Exception:
                    pass

    unique = list(dict.fromkeys(found))
    return drives, unique

def get_music_dir(drive_path):
    """Returns path to the PSP MUSIC directory."""
    return os.path.join(drive_path, "MUSIC")

def get_video_dir(drive_path):
    """Returns path to the PSP VIDEO directory."""
    return os.path.join(drive_path, "VIDEO")

def get_playlist_dir(drive_path, media_type="audio"):
    """Returns path to the PSP PLAYLIST directory for music or video."""
    sub = "MUSIC" if media_type == "audio" else "VIDEO"
    return os.path.join(drive_path, "PSP", "PLAYLIST", sub)

def ensure_psp_dirs(drive_path):
    """Ensures that the standard PSP media directories exist."""
    os.makedirs(get_music_dir(drive_path), exist_ok=True)
    os.makedirs(get_video_dir(drive_path), exist_ok=True)
    os.makedirs(get_playlist_dir(drive_path, "audio"), exist_ok=True)
    os.makedirs(get_playlist_dir(drive_path, "video"), exist_ok=True)
