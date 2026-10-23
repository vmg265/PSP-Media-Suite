import os
import requests
from io import BytesIO
from PIL import Image
import yt_dlp

def get_ydl_opts(browser=None, quiet=True, extract_flat=True, **extra_opts):
    """Constructs standard yt-dlp options dictionary with optional browser cookies and anti-403 player client configuration."""
    opts = {
        'quiet': quiet,
        'extract_flat': extract_flat,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web']
            }
        },
        'retries': 5,
        'fragment_retries': 5,
        'skip_unavailable_fragments': True,
    }
    if browser and browser != "None":
        try:
            opts['cookiesfrombrowser'] = (browser.lower(),)
        except Exception:
            pass

    if 'extractor_args' in extra_opts:
        custom_args = extra_opts.pop('extractor_args')
        if isinstance(custom_args, dict) and 'youtube' in custom_args:
            opts['extractor_args']['youtube'].update(custom_args['youtube'])
        elif isinstance(custom_args, dict):
            opts['extractor_args'].update(custom_args)

    opts.update(extra_opts)
    return opts

def search_youtube(query, browser=None, max_results=24):
    """
    Searches YouTube or inspects a direct URL using yt-dlp.
    Returns a list of entry dicts.
    """
    opts = get_ydl_opts(browser=browser, quiet=True, extract_flat=True)
    with yt_dlp.YoutubeDL(opts) as ydl:
        if query.startswith("http"):
            info = ydl.extract_info(query, download=False)
            if not info:
                return []
            if info.get('_type') == 'playlist' or 'entries' not in info:
                return [info]
            return list(info.get('entries', []))
        else:
            search_target = f"ytsearch{max_results}:{query}"
            info = ydl.extract_info(search_target, download=False)
            if not info:
                return []
            return list(info.get('entries', []))

def search_youtube_paginated(query, page=1, page_size=10, browser=None):
    """Performs paginated search used by the direct PSP web browser interface."""
    fetch_count = page * page_size
    opts = get_ydl_opts(browser=browser, quiet=True, extract_flat=True)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{fetch_count}:{query}", download=False)
        entries = list(info.get('entries', [])) if info else []
    start_idx = (page - 1) * page_size
    return entries[start_idx:fetch_count]

def get_best_thumbnail(info_dict, fallback_url=None):
    """Finds and downloads the highest quality available thumbnail image."""
    urls = []
    if info_dict and info_dict.get('thumbnails'):
        for t in reversed(info_dict['thumbnails']):
            if t.get('url'):
                urls.append(t['url'])
    if info_dict and info_dict.get('thumbnail'):
        urls.append(info_dict['thumbnail'])
    if fallback_url:
        urls.append(fallback_url)

    for u in urls:
        if not u or not u.startswith("http"):
            continue
        try:
            r = requests.get(u, timeout=5)
            if r.status_code == 200:
                try:
                    img = Image.open(BytesIO(r.content))
                    img.verify()
                    return Image.open(BytesIO(r.content))
                except Exception:
                    pass
        except Exception:
            pass
    return None

def fetch_thumbnail_preview(url, size=(80, 45)):
    """Downloads an image URL and returns a resized PIL Image preview."""
    try:
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            return Image.open(BytesIO(r.content)).resize(size)
    except Exception:
        pass
    return None
