import os
import shutil
import threading
import uuid
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from core.config import get_resource_path, clean_filename, format_time
from core.downloader import search_youtube_paginated, get_best_thumbnail, get_ydl_opts
from core.transcoder import (
    get_ffmpeg_path,
    crop_and_save_cover,
    crop_and_save_thm,
    apply_mp3_tags,
    transcode_video_to_psp,
    cleanup_temp_files
)
import yt_dlp

class PSPRequestHandler(BaseHTTPRequestHandler):
    """
    HTTP Request Handler optimized specifically for the legacy PSP NetFront Browser.
    Serves simple HTML tables, handles YouTube searches, and queues media conversions.
    """

    def log_message(self, format, *args):
        # Mute default HTTP request logging to avoid terminal clutter
        pass

    def do_GET(self):
        server_obj = self.server.controller
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        if path == "/":
            self._serve_search_page()

        elif path == "/search":
            q = query.get('q', [''])[0]
            page = int(query.get('page', ['1'])[0])
            if q:
                server_obj.log(f"[PSP] Search requested: {q} (Page {page})")
                self._serve_results_page(q, page, server_obj)
            else:
                self._serve_search_page()

        elif path == "/dl":
            dl_type = query.get('type', [''])[0]
            url = query.get('url', [''])[0]
            title = query.get('title', ['Unknown Video'])[0]
            thumb = query.get('thumb', [''])[0]

            task_id = uuid.uuid4().hex[:8]
            server_obj.web_tasks[task_id] = {
                'status': 'processing',
                'title': urllib.parse.unquote_plus(title),
                'file': None,
                'thm_file': None,
                'type': dl_type
            }

            clean_disp_title = server_obj.web_tasks[task_id]['title'][:30]
            server_obj.log(f"[PSP] Remote process started: {clean_disp_title}...")
            threading.Thread(
                target=server_obj.process_download,
                args=(task_id, dl_type, url, urllib.parse.unquote_plus(thumb)),
                daemon=True
            ).start()

            self.send_response(302)
            self.send_header('Location', f'/status?id={task_id}')
            self.end_headers()

        elif path == "/status":
            task_id = query.get('id', [''])[0]
            task = server_obj.web_tasks.get(task_id)

            if not task:
                self._send_html("Task not found.")
                return

            if task['status'] == 'processing':
                html = f"""<html>
                <head>
                    <title>Processing</title>
                    <meta http-equiv="refresh" content="5">
                </head>
                <body bgcolor="#121212" text="#ffffff" style="font-family: sans-serif; text-align: center; padding-top: 50px;">
                    <h2 style="color: #f59e0b;">Please Wait</h2>
                    <p><b>{task['title'][:40]}...</b></p>
                    <p>Media is being downloaded and converted...</p>
                    <p><font color="#9ca3af">This page will auto-refresh every 5 seconds.</font></p>
                </body></html>"""
                self._send_html(html)

            elif task['status'] == 'done':
                if task['type'] == 'audio':
                    html = f"""<html>
                    <head>
                        <title>Ready</title>
                        <meta http-equiv="refresh" content="0;url=/serve_file?id={task_id}">
                    </head>
                    <body bgcolor="#121212" text="#ffffff" style="font-family: sans-serif; text-align: center; padding-top: 50px;">
                        <h2 style="color: #22c55e;">Ready!</h2>
                        <p>Your file is ready. The download prompt should appear shortly.</p>
                        <p><a href="/serve_file?id={task_id}" style="color: #3b82f6;">Click here if it doesn't start</a></p>
                        <br><br><a href="/" style="color: #9ca3af;">&laquo; Back to Search</a>
                    </body></html>"""
                else:
                    thm_btn = ""
                    if task.get('thm_file'):
                        thm_btn = f'<br><br><br><a href="/serve_file?id={task_id}&ext=thm" style="color: #ffffff; background-color: #f97316; padding: 10px; text-decoration: none; border-radius: 4px;">2. Download Thumbnail (.thm)</a>'

                    html = f"""<html>
                    <head><title>Ready</title></head>
                    <body bgcolor="#121212" text="#ffffff" style="font-family: sans-serif; text-align: center; padding-top: 40px;">
                        <h2 style="color: #22c55e;">Ready!</h2>
                        <p>Video processing complete</p>
                        <p><b>Note:</b> For the PSP to show the video thumbnail, you must download BOTH files below to the VIDEO folder.</p>
                        <br>
                        <a href="/serve_file?id={task_id}" style="color: #ffffff; background-color: #3b82f6; padding: 10px; text-decoration: none; border-radius: 4px;">1. Download Video (.mp4)</a>
                        {thm_btn}
                        <br><br><br><br><a href="/" style="color: #9ca3af;">&laquo; Back to Search</a>
                    </body></html>"""
                self._send_html(html)

            elif task['status'] == 'error':
                html = """<html>
                <body bgcolor="#121212" text="#ffffff" style="font-family: sans-serif; text-align: center; padding-top: 50px;">
                    <h2 style="color: #ef4444;">Error</h2>
                    <p>Failed to process this item on the PC.</p>
                    <br><br><a href="/" style="color: #3b82f6;">&laquo; Back to Search</a>
                </body></html>"""
                self._send_html(html)

        elif path == "/serve_file":
            task_id = query.get('id', [''])[0]
            ext = query.get('ext', [''])[0]
            task = server_obj.web_tasks.get(task_id)

            if not task:
                self.send_response(404)
                self.end_headers()
                return

            filepath = task.get('thm_file') if ext == 'thm' else task.get('file')

            if not filepath or not os.path.exists(filepath):
                self.send_response(404)
                self.end_headers()
                return

            filename = os.path.basename(filepath)
            try:
                with open(filepath, 'rb') as f:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                    self.send_header("Content-Length", str(os.path.getsize(filepath)))
                    self.end_headers()
                    try:
                        shutil.copyfileobj(f, self.wfile)
                    except Exception as stream_e:
                        if "Broken pipe" not in str(stream_e) and "Connection reset" not in str(stream_e):
                            server_obj.log(f"Stream note: {stream_e}")
            except Exception as e:
                if "Broken pipe" not in str(e) and "Connection reset" not in str(e):
                    server_obj.log(f"Error streaming file to PSP: {e}")

    def _send_html(self, html_content):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html_content.encode('utf-8'))

    def _serve_search_page(self):
        html = """<html>
        <head><title>PSP Media Suite</title></head>
        <body bgcolor="#121212" text="#ffffff" style="font-family: sans-serif;">
            <h2 style="color: #3b82f6;">PSP Media Search</h2>
            <form action="/search" method="get">
                <input type="text" name="q" size="30" style="padding: 4px;">
                <input type="submit" value="Search YouTube">
            </form>
        </body></html>"""
        self._send_html(html)

    def _serve_results_page(self, query_str, page, server_obj):
        browser = server_obj.get_browser()
        display_results = search_youtube_paginated(query_str, page=page, page_size=10, browser=browser)

        html = f"""<html>
        <head><title>Results for {query_str}</title></head>
        <body bgcolor="#121212" text="#ffffff" style="font-family: sans-serif; font-size: 12px;">
            <h3>Results for "{query_str}"</h3>
            <a href="/" style="color: #3b82f6;">&laquo; Back to Search</a>
            <hr color="#3f3f46">
            <table width="100%" cellpadding="6" cellspacing="0" border="1" bordercolor="#3f3f46">"""

        for r in display_results:
            vid_id = r.get('id')
            url = f"https://www.youtube.com/watch?v={vid_id}"
            title = r.get('title', 'Unknown').replace('"', "'")
            channel = r.get('uploader', 'Unknown')
            duration = format_time(r.get('duration', 0))

            thumb = r.get('thumbnails', [{'url': ''}])[-1].get('url', '')

            safe_url = urllib.parse.quote(url)
            safe_title = urllib.parse.quote(title)
            safe_thumb = urllib.parse.quote(thumb)

            html += f"""
            <tr>
                <td valign="top">
                    <b>{title[:55]}...</b><br>
                    <font color="#9ca3af">{channel}  ·  {duration}</font>
                </td>
                <td width="110" align="center" valign="middle">
                    <a href="/dl?type=audio&url={safe_url}&title={safe_title}&thumb={safe_thumb}" style="color: #22c55e; font-weight: bold; text-decoration: none;">[ AUDIO ]</a><br><br>
                    <a href="/dl?type=video&url={safe_url}&title={safe_title}&thumb={safe_thumb}" style="color: #f97316; font-weight: bold; text-decoration: none;">[ VIDEO ]</a>
                </td>
            </tr>"""

        safe_query = urllib.parse.quote_plus(query_str)
        html += f"""</table>
        <br>
        <div align="center" style="padding: 10px;">
            <a href="/search?q={safe_query}&page={page + 1}" style="color: #ffffff; font-size: 14px; font-weight: bold; background-color: #3b82f6; text-decoration: none; padding: 6px 12px; border: 1px solid #3b82f6;">&nbsp;Load More Results&nbsp;</a>
        </div>
        <br>
        </body></html>"""
        self._send_html(html)

class PSPServerConfig(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, controller):
        super().__init__(server_address, RequestHandlerClass)
        self.controller = controller

class PSPWebServer:
    """Manages the lifecycle and worker jobs of the embedded PSP web server."""

    def __init__(self, port=8080, log_callback=None, browser_provider=None):
        self.port = port
        self.log_callback = log_callback or (lambda msg: None)
        self.browser_provider = browser_provider or (lambda: "None")
        self.server = None
        self.server_thread = None
        self.web_tasks = {}

    def log(self, message):
        self.log_callback(message)

    def get_browser(self):
        return self.browser_provider()

    def is_running(self):
        return self.server is not None

    def start(self):
        if self.is_running():
            return
        def run():
            self.server = PSPServerConfig(("0.0.0.0", self.port), PSPRequestHandler, self)
            self.server.serve_forever()

        self.server_thread = threading.Thread(target=run, daemon=True)
        self.server_thread.start()

    def stop(self):
        if not self.is_running():
            return
        def _shutdown():
            if self.server:
                self.server.shutdown()
                self.server.server_close()
                self.server = None
        threading.Thread(target=_shutdown, daemon=True).start()

    def process_download(self, task_id, dl_type, url, thumb_url):
        task = self.web_tasks[task_id]
        clean_title = task['title']
        clean_name = clean_filename(clean_title, 80)

        out_dir = os.path.join(get_resource_path(""), "web_out")
        os.makedirs(out_dir, exist_ok=True)

        ff_path = get_ffmpeg_path()
        raw_dl = f"temp_raw_{task_id}.%(ext)s"
        browser = self.get_browser()

        try:
            if dl_type == 'audio':
                opts = get_ydl_opts(
                    browser=browser,
                    quiet=True,
                    extract_flat=False,
                    format='bestaudio/best',
                    ffmpeg_location=ff_path,
                    outtmpl=raw_dl,
                    nopart=True,
                    continuedl=False,
                    postprocessors=[{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
                    postprocessor_args=['-map_metadata', '-1']
                )

                self.log("Downloading audio from YouTube...")
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info_dict = ydl.extract_info(url, download=True)

                img = get_best_thumbnail(info_dict, thumb_url)
                cover_path = f"cover_{task_id}.jpg"
                if img:
                    try:
                        crop_and_save_cover(img, cover_path)
                    except Exception:
                        pass

                dl_file = f"temp_raw_{task_id}.mp3"
                if os.path.exists(dl_file):
                    apply_mp3_tags(dl_file, clean_title, "YouTube Audio", "PSP Media Suite", cover_path)

                    final_path = os.path.join(out_dir, f"{clean_name}.mp3")
                    if os.path.exists(final_path):
                        os.remove(final_path)
                    shutil.move(dl_file, final_path)

                    task['file'] = final_path
                    task['status'] = 'done'
                    self.log(f"[OK] Web Task Ready: {clean_name}.mp3")
                else:
                    raise Exception("Audio extraction failed")

            elif dl_type == 'video':
                opts = get_ydl_opts(
                    browser=browser,
                    quiet=True,
                    extract_flat=False,
                    format='bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    ffmpeg_location=ff_path,
                    outtmpl=raw_dl,
                    nopart=True,
                    continuedl=False
                )

                self.log("Downloading video from YouTube...")
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info_dict = ydl.extract_info(url, download=True)

                raw_file = next((f for f in os.listdir(".") if f.startswith(f"temp_raw_{task_id}") and not f.endswith(".mp3")), None)
                if raw_file:
                    final_path = os.path.join(out_dir, f"{clean_name}.mp4")
                    if os.path.exists(final_path):
                        os.remove(final_path)
                    transcode_video_to_psp(raw_file, final_path)
                    task['file'] = final_path

                    img = get_best_thumbnail(info_dict, thumb_url)
                    if img:
                        try:
                            thm_path = os.path.join(out_dir, f"{clean_name}.thm")
                            crop_and_save_thm(img, thm_path)
                            task['thm_file'] = thm_path
                        except Exception as e:
                            self.log(f".THM Error: {str(e)[:40]}")

                    task['status'] = 'done'
                    self.log(f"[OK] Web Task Ready: {clean_name}.mp4")
                else:
                    raise Exception("Video download failed")

        except Exception as e:
            self.log(f"[ERROR] Web Processing Error: {e}")
            task['status'] = 'error'

        finally:
            cleanup_temp_files(".", task_id=task_id)
