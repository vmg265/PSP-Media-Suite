import os, sys, shutil, threading, psutil, requests, subprocess, tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageTk, ImageDraw
from io import BytesIO
import yt_dlp

from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB

def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class PSPMediaSuite:
    def __init__(self, root):
        self.root = root
        self.root.title("PSP Media Tool v1.4p")
        
        try:
            self.root.state('zoomed')
        except tk.TclError:
            self.root.attributes('-zoomed', True)
        
        self.bg_color = "#ffffff"
        self.root.configure(bg=self.bg_color)
        
        self.drives = {}
        self.queue = []
        self.photo_references = [] 
        self.is_processing = False

        style = ttk.Style()
        style.theme_use('default')
        style.configure('TNotebook.Tab', background='#d0d0d0', padding=[20, 5], font=('MS Sans Serif', 10, 'bold'))
        style.map('TNotebook.Tab', background=[('selected', '#00ccff')], foreground=[('selected', 'black')])

        header_container = tk.Frame(root, bg=self.bg_color)
        header_container.pack(fill="x", padx=20, pady=10)

        self.banner_canvas = tk.Canvas(header_container, bg=self.bg_color, highlightthickness=0, height=120)
        self.banner_canvas.pack(side="left", fill="x", expand=True, padx=(0, 20))
        self.banner_canvas.bind("<Configure>", self.resize_banner)

        right_panel = tk.Frame(header_container, bg=self.bg_color)
        right_panel.pack(side="right", anchor="center")
        
        radio_frame = tk.Frame(right_panel, bg=self.bg_color)
        radio_frame.pack(anchor="e", pady=2)
        self.storage_mode = tk.StringVar(value="ms0")
        tk.Radiobutton(radio_frame, text="PSP 1000-3000", variable=self.storage_mode, value="ms0", bg=self.bg_color, command=self.scan_usb).pack(side="left")
        tk.Radiobutton(radio_frame, text="PSP Go Internal", variable=self.storage_mode, value="ef0", bg=self.bg_color, command=self.scan_usb).pack(side="left")

        drive_frame = tk.Frame(right_panel, bg=self.bg_color)
        drive_frame.pack(anchor="e", pady=2)
        self.drive_combo = ttk.Combobox(drive_frame, state="readonly", width=25)
        self.drive_combo.pack(side="left", padx=5)
        tk.Button(drive_frame, text="🔄 REFRESH", command=self.scan_usb, bg="#e0e0e0", font=("Arial", 8)).pack(side="left")

        main_content = tk.Frame(root, bg=self.bg_color)
        main_content.pack(fill="both", expand=True, padx=20)

        left_col = tk.Frame(main_content, bg=self.bg_color)
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.notebook = ttk.Notebook(left_col)
        self.notebook.pack(fill="both", expand=True)
        
        self.tab_music = tk.Frame(self.notebook, bg=self.bg_color)
        self.tab_video = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.tab_music, text="🎵 MUSIC")
        self.notebook.add(self.tab_video, text="🎬 VIDEO")

        self.setup_tab(self.tab_music, "audio")
        self.setup_tab(self.tab_video, "video")

        right_col = tk.Frame(main_content, bg=self.bg_color)
        right_col.pack(side="right", fill="both", expand=True, padx=(10, 0))

        queue_label_frame = tk.LabelFrame(right_col, text="Transfer Queue", bg=self.bg_color, font=("MS Sans Serif", 10, "bold"))
        queue_label_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.queue_canvas = tk.Canvas(queue_label_frame, bg="#f0f0f0", highlightthickness=0)
        queue_scroll = tk.Scrollbar(queue_label_frame, orient="vertical", command=self.queue_canvas.yview)
        self.queue_frame = tk.Frame(self.queue_canvas, bg="#f0f0f0")
        self.queue_canvas.create_window((0,0), window=self.queue_frame, anchor="nw")
        self.queue_canvas.configure(yscrollcommand=queue_scroll.set)
        self.queue_canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        queue_scroll.pack(side="right", fill="y")

        log_frame = tk.LabelFrame(right_col, text="System Logs", bg=self.bg_color, font=("MS Sans Serif", 9), height=150)
        log_frame.pack(fill="x")
        log_frame.pack_propagate(False)
        
        self.log_text = tk.Text(log_frame, bg="#f8f8f8", fg="grey", font=("Consolas", 8), state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

        self.progress = ttk.Progressbar(root, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", padx=20, pady=5)

        self.push_btn_canvas = tk.Canvas(root, bg=self.bg_color, highlightthickness=0, height=50)
        self.push_btn_canvas.pack(fill="x", padx=20, pady=10)
        self.push_btn_canvas.bind("<Configure>", self.draw_push_btn)
        
        self.btn_state = "normal"
        self.btn_text = "SEND QUEUE TO PSP"

        self.scan_usb()

    def write_log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"> {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def resize_banner(self, event):
        banner_path = get_resource_path("banner.png")
        if not os.path.exists(banner_path):
            return
        w = event.width
        h = event.height
        if w <= 20:
            return

        try:
            img = Image.open(banner_path)
            target_w = w - 10
            ratio = target_w / float(img.size[0])
            new_h = int(img.size[1] * ratio)
            
            try:
                resample_filter = Image.Resampling.LANCZOS
            except AttributeError:
                resample_filter = Image.LANCZOS
                
            img = img.resize((target_w, new_h), resample_filter)
            
            if new_h > h:
                top_crop = (new_h - h) // 2
                img = img.crop((0, top_crop, target_w, top_crop + h))
            
            mask = Image.new('L', img.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.size[0], img.size[1]), 12, fill=255)
            img.putalpha(mask)
            
            self.banner_photo = ImageTk.PhotoImage(img)
            self.banner_canvas.delete("all")
            self.banner_canvas.create_image(0, 0, anchor="nw", image=self.banner_photo)
            self.banner_canvas.create_text(25, h/2, text="PSP-Media Suite", font=("MS Sans Serif", 24, "bold"), fill="white", anchor="w")
        except:
            pass

    def scan_usb(self):
        self.drives = {}
        found = []
        for part in psutil.disk_partitions(all=True):
            try:
                if os.path.exists(os.path.join(part.mountpoint, "PSP")):
                    size = psutil.disk_usage(part.mountpoint).total / (1024**3)
                    name = f"{(os.path.basename(part.mountpoint) or part.mountpoint)} ({size:.1f}GB)"
                    self.drives[name] = part.mountpoint
                    found.append(name)
            except:
                continue
        
        if os.name != 'nt':
            for base in ["/media", "/run/media", "/mnt/chromeos/removable"]:
                if os.path.exists(base):
                    try:
                        for u in os.listdir(base):
                            p = os.path.join(base, u)
                            if os.path.isdir(p) and os.path.exists(os.path.join(p, "PSP")):
                                n = f"External ({u})"
                                self.drives[n] = p
                                found.append(n)
                    except:
                        pass

        self.drive_combo['values'] = list(set(found))
        if found:
            self.drive_combo.current(0)
        else:
            self.drive_combo.set("No Drive Found")

    def format_time(self, seconds):
        if not seconds:
            return "??:??"
        try:
            seconds = int(seconds)
            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            if h > 0:
                return f"{h}:{m:02d}:{s:02d}"
            return f"{m}:{s:02d}"
        except:
            return "??:??"

    def setup_tab(self, parent, media_type):
        search_var = tk.StringVar()
        entry = tk.Entry(parent, textvariable=search_var, fg="grey", font=("MS Sans Serif", 12), borderwidth=2, relief="sunken")
        entry.insert(0, "Search YouTube...")
        entry.bind("<FocusIn>", lambda e: self.clear_ph(entry))
        entry.bind("<FocusOut>", lambda e: self.add_ph(entry))
        entry.bind('<Return>', lambda e: self.search(search_var.get(), parent, media_type))
        entry.pack(fill="x", padx=10, pady=10)

        results_canvas = tk.Canvas(parent, bg="#fff", highlightthickness=1)
        scroll = tk.Scrollbar(parent, orient="vertical", command=results_canvas.yview)
        results_frame = tk.Frame(results_canvas, bg="#fff")
        
        parent.results_canvas = results_canvas
        parent.results_frame = results_frame
        parent.cached_results = []
        parent.render_index = 0
        parent.load_more_btn = None
        
        results_canvas.create_window((0,0), window=results_frame, anchor="nw")
        results_canvas.configure(yscrollcommand=scroll.set)
        results_canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        scroll.pack(side="right", fill="y", pady=5)
        self.bind_mousewheel(results_canvas, results_frame)

    def bind_mousewheel(self, canvas, frame):
        def _on_mousewheel(event):
            if sys.platform == "darwin":
                canvas.yview_scroll(int(-1*(event.delta)), "units")
            elif event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
            else:
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_mousewheel)
        canvas.bind_all("<Button-5>", _on_mousewheel)

    def clear_ph(self, entry):
        if entry.get() == "Search YouTube...":
            entry.delete(0, tk.END)
            entry.config(fg="black")

    def add_ph(self, entry):
        if not entry.get():
            entry.insert(0, "Search YouTube...")
            entry.config(fg="grey")

    def fetch_image_bytes(self, url):
        try:
            resp = requests.get(url, timeout=3)
            return Image.open(BytesIO(resp.content)).resize((80, 45))
        except:
            return None

    def search(self, q, parent, media_type):
        if q == "Search YouTube...":
            return
        for widget in parent.results_frame.winfo_children():
            widget.destroy()
        parent.cached_results = []
        parent.render_index = 0
        self.progress['value'] = 20
        threading.Thread(target=self._search_thread, args=(q, parent, media_type), daemon=True).start()

    def _search_thread(self, q, parent, media_type):
        opts = {'quiet': True, 'extract_flat': True}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = list(ydl.extract_info(f"ytsearch24:{q}", download=False)['entries'])
            parent.cached_results = info
            self.root.after(0, self.trigger_load_chunk, parent, media_type)
        except Exception as e:
            self.root.after(0, lambda: self.progress.configure(value=0))
            self.root.after(0, lambda: self.write_log(f"Search failed: {e}"))

    def trigger_load_chunk(self, parent, media_type):
        if parent.load_more_btn:
            parent.load_more_btn.destroy()
            parent.load_more_btn = None
            
        self.progress['value'] = 40
        threading.Thread(target=self._load_chunk_thread, args=(parent, media_type), daemon=True).start()

    def _load_chunk_thread(self, parent, media_type):
        start = parent.render_index
        end = start + 8
        chunk = parent.cached_results[start:end]
        
        for r in chunk:
            if 'url' not in r and 'id' in r:
                r['url'] = f"https://www.youtube.com/watch?v={r['id']}"
            elif 'url' not in r:
                r['url'] = ""
            
            thumb_url = r.get('thumbnail')
            if not thumb_url and r.get('thumbnails'):
                thumb_url = r['thumbnails'][-1].get('url')
            
            r['raw_thumb_url'] = thumb_url 
            r['pil_image'] = self.fetch_image_bytes(thumb_url) if thumb_url else None
            r['formatted_time'] = self.format_time(r.get('duration'))
            
        self.root.after(0, self.render_chunk, chunk, parent, media_type)

    def render_chunk(self, chunk, parent, media_type):
        for item in chunk:
            if not item.get('url'):
                continue
            
            row = tk.Frame(parent.results_frame, bg="white", pady=5)
            row.pack(fill="x", anchor="w")
            
            if item.get('pil_image'):
                photo = ImageTk.PhotoImage(item['pil_image'])
                self.photo_references.append(photo)
                tk.Label(row, image=photo, bg="white").pack(side="left", padx=10)
            
            display_text = f"{item['title'][:65]}  [{item['formatted_time']}]"
            tk.Label(row, text=display_text, bg="white", font=("Arial", 10)).pack(side="left", padx=5)
            
            btn_text = "➕ Add Music" if media_type == "audio" else "➕ Add Video"
            btn_color = "#ccffcc" if media_type == "audio" else "#ffffcc"
            tk.Button(row, text=btn_text, bg=btn_color, command=lambda i=item, mt=media_type: self.add_to_queue(i, mt)).pack(side="right", padx=10)
            
        parent.render_index += 8
        
        if parent.render_index < len(parent.cached_results):
            parent.load_more_btn = tk.Button(parent.results_frame, text="🔽 LOAD MORE", command=lambda: self.trigger_load_chunk(parent, media_type), bg="#e0e0e0", font=("Arial", 10, "bold"), pady=5)
            parent.load_more_btn.pack(pady=10)
            
        self.root.update_idletasks()
        parent.results_canvas.configure(scrollregion=parent.results_canvas.bbox("all"))
        self.progress['value'] = 100

    def add_to_queue(self, item, media_type):
        q_row = tk.Frame(self.queue_frame, bg="#f0f0f0", pady=2)
        q_row.pack(fill="x", anchor="w")
        
        icon = "🎵 " if media_type == "audio" else "🎬 "
        
        if item.get('pil_image'):
            photo = ImageTk.PhotoImage(item['pil_image'].resize((50, 28)))
            self.photo_references.append(photo)
            tk.Label(q_row, image=photo, bg="#f0f0f0").pack(side="left", padx=5)
            
        q_text = f"{icon} [{item['formatted_time']}] {item['title'][:50]}"
        lbl = tk.Label(q_row, text=q_text, bg="#f0f0f0", font=("Arial", 9))
        lbl.pack(side="left")
        
        btn = tk.Button(q_row, text="❌", bg="#ffcccc", relief="flat", command=lambda: self.remove_from_queue(q_row, q_data))
        btn.pack(side="right", padx=10)
        
        q_data = {
            'status': 'pending',
            'type': media_type, 
            'url': item['url'], 
            'title': item['title'], 
            'thumb': item.get('raw_thumb_url'),
            'lbl': lbl,
            'btn': btn
        }
        
        self.queue.append(q_data)
        self.root.update_idletasks()
        self.queue_canvas.configure(scrollregion=self.queue_canvas.bbox("all"))

    def remove_from_queue(self, row_widget, q_data):
        row_widget.destroy()
        if q_data in self.queue:
            self.queue.remove(q_data)
        self.root.update_idletasks()
        self.queue_canvas.configure(scrollregion=self.queue_canvas.bbox("all"))

    def draw_push_btn(self, event=None):
        self.push_btn_canvas.delete("all")
        w = self.push_btn_canvas.winfo_width()
        h = self.push_btn_canvas.winfo_height()
        if w <= 1 or h <= 1:
            return
        rad = 12
        color = "#00ccff" if self.btn_state == "normal" else "#a0a0a0"
        if self.is_processing:
            color = "#ffff00"
        
        self.push_btn_canvas.create_arc(0, 0, rad*2, rad*2, start=90, extent=90, fill=color, outline="")
        self.push_btn_canvas.create_arc(w-rad*2, 0, w, rad*2, start=0, extent=90, fill=color, outline="")
        self.push_btn_canvas.create_arc(0, h-rad*2, rad*2, h, start=180, extent=90, fill=color, outline="")
        self.push_btn_canvas.create_arc(w-rad*2, h-rad*2, w, h, start=270, extent=90, fill=color, outline="")
        self.push_btn_canvas.create_rectangle(rad, 0, w-rad, h, fill=color, outline="")
        self.push_btn_canvas.create_rectangle(0, rad, w, h-rad, fill=color, outline="")
        self.push_btn_canvas.create_text(w/2, h/2, text=self.btn_text, font=("MS Sans Serif", 14, "bold"), fill="black")
        
        self.push_btn_canvas.bind("<Button-1>", lambda e: self.process_queue() if self.btn_state == "normal" else None)

    def update_push_btn(self, text, state):
        self.btn_text = text
        self.btn_state = state
        self.draw_push_btn()

    def process_queue(self):
        drive_name = self.drive_combo.get()
        if drive_name not in self.drives or not self.queue:
            return
        
        self.is_processing = True
        self.update_push_btn("PROCESSING...", "disabled")
        threading.Thread(target=self._process_queue, args=(self.drives[drive_name],), daemon=True).start()

    def _process_queue(self, drive_path):
        ff_path = get_resource_path("ffmpeg" if os.name != 'nt' else "ffmpeg.exe")
        total = len(self.queue)
        
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        for i, item in enumerate(self.queue):
            if item['status'] == 'success':
                continue
            
            self.root.after(0, lambda v=(i/total)*100: self.progress.configure(value=v))
            self.root.after(0, lambda msg=f"Processing: {item['title'][:40]}": self.write_log(msg))
            
            clean_name = "".join(x for x in item['title'] if x.isalnum() or x in " .-_")[:100]
            
            try:
                if item['type'] == 'audio':
                    target_dir = os.path.join(drive_path, "MUSIC")
                    if not os.path.exists(target_dir):
                        os.makedirs(target_dir)
                    
                    opts = {
                        'format': 'bestaudio/best',
                        'ffmpeg_location': ff_path,
                        'outtmpl': 'temp_raw.%(ext)s',
                        'nopart': True,
                        'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
                        'postprocessor_args': ['-map_metadata', '-1'] 
                    }
                    
                    with yt_dlp.YoutubeDL(opts) as ydl: 
                        info_dict = ydl.extract_info(item['url'], download=True)
                        
                        best_thumb = None
                        if info_dict.get('thumbnails'):
                            best_thumb = info_dict['thumbnails'][-1]['url']
                        else:
                            best_thumb = info_dict.get('thumbnail')
                    
                    has_cover = False
                    if best_thumb:
                        try:
                            resp = requests.get(best_thumb, timeout=10)
                            img = Image.open(BytesIO(resp.content))
                            width, height = img.size
                            new_size = min(width, height)
                            left = (width - new_size)/2
                            top = (height - new_size)/2
                            right = (width + new_size)/2
                            bottom = (height + new_size)/2
                            img = img.crop((left, top, right, bottom))
                            
                            try:
                                resample_filter = Image.Resampling.LANCZOS
                            except AttributeError:
                                resample_filter = Image.LANCZOS
                            
                            img = img.resize((600, 600), resample_filter)
                            img.convert('RGB').save("cover.jpg", format='JPEG', quality=85, optimize=False, progressive=False)
                            has_cover = True
                        except Exception as e:
                            self.write_log(f"Cover Error: {e}")
                    
                    audio = MP3("temp_raw.mp3", ID3=ID3)
                    
                    if audio.tags is None:
                        audio.add_tags()
                    else:
                        audio.tags.clear()
                    
                    audio.tags.add(TIT2(encoding=3, text=item["title"]))
                    audio.tags.add(TPE1(encoding=3, text="YouTube Audio"))
                    audio.tags.add(TALB(encoding=3, text="PSP Media Suite"))
                    
                    if has_cover:
                        with open("cover.jpg", "rb") as albumart:
                            audio.tags.add(
                                APIC(
                                    encoding=3,
                                    mime='image/jpeg',
                                    type=3,
                                    desc='Cover',
                                    data=albumart.read()
                                )
                            )
                    
                    audio.save(v2_version=3, v1=2) 
                    shutil.move("temp_raw.mp3", os.path.join(target_dir, clean_name + ".mp3"))
                
                else:
                    target_dir = os.path.join(drive_path, "VIDEO")
                    if not os.path.exists(target_dir):
                        os.makedirs(target_dir)
                    
                    opts = {
                        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                        'ffmpeg_location': ff_path,
                        'outtmpl': 'temp.%(ext)s',
                        'nopart': True,
                        'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}],
                        'postprocessor_args': [
                            '-c:v', 'libx264', '-profile:v', 'baseline', '-level', '3.0',
                            '-pix_fmt', 'yuv420p', '-vf', 'scale=480:272', '-b:v', '768k',
                            '-c:a', 'aac', '-b:a', '128k', '-ar', '48000'
                        ]
                    }
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info_dict = ydl.extract_info(item['url'], download=True)
                        
                        best_thumb = None
                        if info_dict.get('thumbnails'):
                            best_thumb = info_dict['thumbnails'][-1]['url']
                        else:
                            best_thumb = info_dict.get('thumbnail')
                            
                        if best_thumb:
                            try:
                                r_thumb = requests.get(best_thumb, timeout=10)
                                img = Image.open(BytesIO(r_thumb.content))
                                width, height = img.size
                                target_ratio = 160 / 120.0
                                current_ratio = width / height
                                
                                if current_ratio > target_ratio:
                                    new_width = int(target_ratio * height)
                                    left = (width - new_width) / 2
                                    img = img.crop((left, 0, left + new_width, height))
                                else:
                                    new_height = int(width / target_ratio)
                                    top = (height - new_height) / 2
                                    img = img.crop((0, top, width, top + new_height))
                                    
                                try: resample_filter = Image.Resampling.LANCZOS
                                except AttributeError: resample_filter = Image.LANCZOS
                                
                                img = img.resize((160, 120), resample_filter)
                                img.convert('RGB').save(os.path.join(target_dir, clean_name + ".thm"), "JPEG")
                            except Exception as e:
                                self.write_log(f".THM Error: {e}")

                    shutil.move("temp.mp4", os.path.join(target_dir, clean_name + ".mp4"))

                item['status'] = 'success'
                self.root.after(0, lambda i=item: i['btn'].config(text="✓", state="disabled", bg="#ccffcc"))

            except Exception as e:
                self.write_log(f"Transfer Error: {e}")
                item['status'] = 'error'
                self.root.after(0, lambda i=item: i['btn'].config(text="X", bg="#ffcccc"))
            
            for ext_clean in ['.mp3', '.mp4', '.jpg', '.webp', '.m4a', '.webm', '.png']:
                if os.path.exists(f"temp{ext_clean}"):
                    os.remove(f"temp{ext_clean}")
                if os.path.exists(f"temp_raw.{ext_clean}"):
                    os.remove(f"temp_raw.{ext_clean}")
            if os.path.exists("cover.jpg"):
                os.remove("cover.jpg")

        self.is_processing = False 
        self.root.after(0, lambda: self.progress.configure(value=100))
        self.root.after(0, lambda: self.update_push_btn("SEND QUEUE TO PSP", "normal"))
        self.root.after(0, lambda: messagebox.showinfo("Queue Complete", "Processing finished! Check queue for statuses."))

if __name__ == "__main__":
    root = tk.Tk()
    app = PSPMediaSuite(root)
    root.mainloop()
