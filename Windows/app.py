import os, sys, shutil, threading, psutil, requests, subprocess, tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageTk
from io import BytesIO
import yt_dlp

from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB

def get_resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class PSPMediaSuite:
    def __init__(self, root):
        self.root = root
        self.root.title("PSP Media Tool")
        
        try: self.root.state('zoomed')
        except tk.TclError: self.root.attributes('-zoomed', True)
        
        self.bg_color = "#ffffff"
        self.root.configure(bg=self.bg_color)
        
        self.drives = {}
        self.queue = []
        self.photo_references = [] 
        self.is_processing = False

        # --- TAB STYLING ---
        style = ttk.Style()
        style.theme_use('default')
        style.configure('TNotebook.Tab', background='#d0d0d0', padding=[20, 5], font=('MS Sans Serif', 10, 'bold'))
        style.map('TNotebook.Tab', background=[('selected', '#00ccff')], foreground=[('selected', 'black')])

        # --- HEADER & STORAGE ---
        top_frame = tk.Frame(root, bg=self.bg_color)
        top_frame.pack(fill="x", padx=20, pady=10)

        left_panel = tk.Frame(top_frame, bg=self.bg_color)
        left_panel.pack(side="left", anchor="nw")
        tk.Label(left_panel, text="PSP Media Suite", font=("MS Sans Serif", 24, "bold"), bg=self.bg_color).pack(anchor="w")

        right_panel = tk.Frame(top_frame, bg=self.bg_color)
        right_panel.pack(side="right", anchor="ne")
        
        radio_frame = tk.Frame(right_panel, bg=self.bg_color)
        radio_frame.pack(anchor="e", pady=2)
        tk.Label(radio_frame, text="Storage Type:", bg=self.bg_color, font=("Arial", 9, "bold")).pack(side="left", padx=5)
        
        self.storage_mode = tk.StringVar(value="ms0")
        tk.Radiobutton(radio_frame, text="PSP 1000-3000 (ms0:/)", variable=self.storage_mode, value="ms0", bg=self.bg_color, command=self.scan_usb).pack(side="left")
        tk.Radiobutton(radio_frame, text="PSP Go Internal (ef0:/)", variable=self.storage_mode, value="ef0", bg=self.bg_color, command=self.scan_usb).pack(side="left")

        drive_frame = tk.Frame(right_panel, bg=self.bg_color)
        drive_frame.pack(anchor="e", pady=2)
        tk.Label(drive_frame, text="Connected Drive:", bg=self.bg_color, font=("Arial", 9, "bold")).pack(side="left", padx=5)
        self.drive_combo = ttk.Combobox(drive_frame, state="readonly", width=30)
        self.drive_combo.pack(side="left")
        tk.Button(drive_frame, text="🔄 REFRESH", command=self.scan_usb, bg="#e0e0e0", font=("Arial", 8)).pack(side="left", padx=5)

        # --- TABS (MUSIC & VIDEO) ---
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=5)
        
        self.tab_music = tk.Frame(self.notebook, bg=self.bg_color)
        self.tab_video = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.tab_music, text="🎵 MUSIC")
        self.notebook.add(self.tab_video, text="🎬 VIDEO")

        self.setup_tab(self.tab_music, "audio")
        self.setup_tab(self.tab_video, "video")

        # --- VISUAL QUEUE ---
        queue_label_frame = tk.LabelFrame(root, text="Transfer Queue", bg=self.bg_color, font=("MS Sans Serif", 10, "bold"))
        queue_label_frame.pack(fill="x", padx=20, pady=5)
        
        self.queue_canvas = tk.Canvas(queue_label_frame, bg="#f0f0f0", height=100, highlightthickness=0)
        queue_scroll = tk.Scrollbar(queue_label_frame, orient="vertical", command=self.queue_canvas.yview)
        self.queue_frame = tk.Frame(self.queue_canvas, bg="#f0f0f0")
        
        self.queue_canvas.create_window((0,0), window=self.queue_frame, anchor="nw")
        self.queue_canvas.configure(yscrollcommand=queue_scroll.set)
        
        self.queue_canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        queue_scroll.pack(side="right", fill="y")

        # --- FOOTER ---
        self.progress = ttk.Progressbar(root, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", padx=20, pady=5)

        self.push_btn = tk.Button(root, text="SEND QUEUE TO PSP", command=self.process_queue, bg="#00ccff", font=("MS Sans Serif", 14, "bold"), height=2)
        self.push_btn.pack(fill="x", padx=20, pady=10)

        self.scan_usb()

    def format_time(self, seconds):
        if not seconds: return "??:??"
        try:
            seconds = int(seconds)
            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            if h > 0: return f"{h}:{m:02d}:{s:02d}"
            return f"{m}:{s:02d}"
        except: return "??:??"

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
        
        results_canvas.create_window((0,0), window=results_frame, anchor="nw")
        results_canvas.configure(yscrollcommand=scroll.set)
        
        results_canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        scroll.pack(side="right", fill="y", pady=5)
        
        self.bind_mousewheel(results_canvas, results_frame)

        parent.results_frame = results_frame
        parent.results_canvas = results_canvas
        parent.cached_results = []
        parent.render_index = 0
        parent.load_more_btn = None

    def bind_mousewheel(self, canvas, frame):
        def _on_mousewheel(event):
            if sys.platform == "darwin": canvas.yview_scroll(int(-1*(event.delta)), "units")
            elif event.num == 4: canvas.yview_scroll(-1, "units")
            elif event.num == 5: canvas.yview_scroll(1, "units")
            else: canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
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

    def scan_usb(self):
        self.drives = {}
        found = []
        for part in psutil.disk_partitions():
            try: self.check_path(part.mountpoint, found)
            except: continue
        if os.path.exists("/mnt/chromeos/removable/"):
            for f in os.listdir("/mnt/chromeos/removable/"):
                self.check_path(os.path.join("/mnt/chromeos/removable/", f), found)
        
        self.drive_combo['values'] = found
        if found: self.drive_combo.current(0)
        else: self.drive_combo.set("No Drive Found")

    def check_path(self, path, found_list):
        if os.path.exists(os.path.join(path, "PSP")):
            size = psutil.disk_usage(path).total / (1024**3)
            name = f"Drive ({os.path.basename(path)}) - {size:.1f}GB"
            self.drives[name] = path
            found_list.append(name)

    def fetch_image_bytes(self, url):
        try:
            resp = requests.get(url, timeout=3)
            return Image.open(BytesIO(resp.content)).resize((80, 45))
        except: return None

    def search(self, q, parent, media_type):
        if q == "Search YouTube...": return
        for widget in parent.results_frame.winfo_children(): widget.destroy()
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
            print(f"Search thread failed: {e}") 
            self.root.after(0, lambda: self.progress.configure(value=0))

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
            if 'url' not in r and 'id' in r: r['url'] = f"https://www.youtube.com/watch?v={r['id']}"
            elif 'url' not in r: r['url'] = ""
            
            thumb_url = r.get('thumbnail')
            if not thumb_url and r.get('thumbnails'):
                thumb_url = r['thumbnails'][-1].get('url')
            
            r['raw_thumb_url'] = thumb_url 
            r['pil_image'] = self.fetch_image_bytes(thumb_url) if thumb_url else None
            r['formatted_time'] = self.format_time(r.get('duration'))
            
        self.root.after(0, self.render_chunk, chunk, parent, media_type)

    def render_chunk(self, chunk, parent, media_type):
        for item in chunk:
            if not item.get('url'): continue
            
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
        tk.Label(q_row, text=q_text, bg="#f0f0f0", font=("Arial", 9)).pack(side="left")
        
        queue_item = {
            'type': media_type, 
            'url': item['url'], 
            'title': item['title'], 
            'thumb': item.get('raw_thumb_url')
        }
        tk.Button(q_row, text="❌", bg="#ffcccc", relief="flat", command=lambda r=q_row, u=item['url']: self.remove_from_queue(r, u)).pack(side="right", padx=10)
        
        self.queue.append(queue_item)
        self.root.update_idletasks()
        self.queue_canvas.configure(scrollregion=self.queue_canvas.bbox("all"))

    def remove_from_queue(self, row_widget, url):
        row_widget.destroy()
        self.queue = [q for q in self.queue if q['url'] != url]
        self.root.update_idletasks()
        self.queue_canvas.configure(scrollregion=self.queue_canvas.bbox("all"))

    def animate_processing_btn(self):
        if not self.is_processing:
            self.push_btn.config(text="SEND QUEUE TO PSP", bg="#00ccff")
            return
            
        current_text = self.push_btn.cget("text")
        if current_text.endswith("..."):
            self.push_btn.config(text="PROCESSING QUEUE", bg="#ffff00")
        else:
            self.push_btn.config(text=current_text + ".")
            
        self.root.after(500, self.animate_processing_btn)

    def process_queue(self):
        drive_name = self.drive_combo.get()
        if drive_name not in self.drives or not self.queue: return
        
        self.is_processing = True
        self.push_btn.config(state="disabled")
        self.animate_processing_btn() 
        
        threading.Thread(target=self._process_queue, args=(self.drives[drive_name],), daemon=True).start()

    def _process_queue(self, drive_path):
        ff_path = get_resource_path("ffmpeg" if os.name != 'nt' else "ffmpeg.exe")
        total = len(self.queue)
        
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        for i, item in enumerate(self.queue):
            self.root.after(0, lambda v=(i/total)*100: self.progress.configure(value=v))
            clean_name = "".join(x for x in item['title'] if x.isalnum() or x in " .-_")[:45]
            
            try:
                if item['type'] == 'audio':
                    target_dir = os.path.join(drive_path, "MUSIC")
                    if not os.path.exists(target_dir): os.makedirs(target_dir)
                    
                    opts = {
                        'format': 'bestaudio/best',
                        'ffmpeg_location': ff_path,
                        'outtmpl': 'temp_raw.%(ext)s',
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
                            
                            try: resample_filter = Image.Resampling.LANCZOS
                            except AttributeError: resample_filter = Image.LANCZOS
                            
                            img = img.resize((600, 600), resample_filter)
                            img.convert('RGB').save("cover.jpg", format='JPEG', quality=85, optimize=False, progressive=False)
                            has_cover = True
                        except Exception as e: print(f"Cover Generation Error: {e}")
                    
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
                    if not os.path.exists(target_dir): os.makedirs(target_dir)
                    
                    opts = {
                        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                        'ffmpeg_location': ff_path,
                        'outtmpl': 'temp.%(ext)s',
                        'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}],
                        'postprocessor_args': [
                            '-c:v', 'libx264', '-profile:v', 'baseline', '-level', '3.0',
                            '-pix_fmt', 'yuv420p', '-vf', 'scale=480:272', '-b:v', '768k',
                            '-c:a', 'aac', '-b:a', '128k', '-ar', '48000'
                        ]
                    }
                    with yt_dlp.YoutubeDL(opts) as ydl: ydl.download([item['url']])
                    shutil.move("temp.mp4", os.path.join(target_dir, clean_name + ".mp4"))

            except Exception as e:
                print(f"Transfer Error on {item['title']}: {e}")
            
            for ext_clean in ['.mp3', '.mp4', '.jpg', '.webp', '.m4a', '.webm', '.png']:
                if os.path.exists(f"temp{ext_clean}"): os.remove(f"temp{ext_clean}")
                if os.path.exists(f"temp_raw.{ext_clean}"): os.remove(f"temp_raw.{ext_clean}")
            if os.path.exists("cover.jpg"): os.remove("cover.jpg")

        self.queue.clear()
        self.is_processing = False 
        
        self.root.after(0, lambda: [w.destroy() for w in self.queue_frame.winfo_children()])
        self.root.after(0, lambda: self.progress.configure(value=100))
        self.root.after(0, lambda: self.push_btn.config(state="normal"))
        self.root.after(0, lambda: messagebox.showinfo("Queue Complete", "All media pushed to PSP!"))

if __name__ == "__main__":
    root = tk.Tk()
    PSPMediaSuite(root)
    root.mainloop()
