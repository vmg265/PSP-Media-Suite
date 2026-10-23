import os
import sys
import json
import socket

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".psp_media_suite_prefs.json")

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_local_ip():
    """Retrieve the primary local IP address of the host machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def load_preferences():
    """Load user preferences from JSON config file."""
    prefs = {
        "browser": "None",
        "dark_mode": True
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                prefs["browser"] = data.get("browser", "None")
                prefs["dark_mode"] = data.get("dark_mode", True)
        except Exception:
            pass
    return prefs

def save_preferences(browser, dark_mode):
    """Save user preferences to JSON config file."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "browser": browser,
                "dark_mode": dark_mode
            }, f, indent=2)
        return True, None
    except Exception as ex:
        return False, str(ex)

def clean_filename(name, max_len=100):
    """Sanitize a string to be a safe filesystem name for PSP storage."""
    safe = "".join(x for x in name if x.isalnum() or x in " .-_")
    return safe[:max_len].strip()

def format_time(seconds):
    """Format duration in seconds to standard 'MM:SS' or 'H:MM:SS' string."""
    if not seconds:
        return "??:??"
    try:
        s = int(seconds)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
    except Exception:
        return "??:??"
