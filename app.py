import os, sys, shutil, threading, psutil, requests, subprocess, webbrowser, time, math, tkinter as tk
from tkinter import messagebox, ttk, filedialog, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFilter
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

# Colors
BG       = "#121212"  
SURFACE  = "#1e1e1e"  
SURFACE2 = "#2d2d30"  
BORDER   = "#3f3f46"  
ACCENT   = "#3b82f6"  
ACCENT2  = "#f97316"  
TEXT     = "#f3f4f6"  
TEXT_DIM = "#9ca3af"  
SUCCESS  = "#22c55e"  
ERROR    = "#ef4444"  
WARN     = "#f59e0b"  

FONT_TITLE  = ("Segoe UI", 22, "bold")
FONT_BODY   = ("Segoe UI", 10)
FONT_SMALL  = ("Segoe UI", 8)
FONT_MONO   = ("Consolas", 9)
FONT_BTN    = ("Segoe UI", 10, "bold")
FONT_TAB    = ("Segoe UI", 10, "bold")


class PSPMediaSuite:
    def __init__(self, root):
        self.root = root
        self.root.title("PSP Media Suite v1.6")
        self.root.minsize(1020, 640)

        try:
            self.root.state('zoomed')
        except tk.TclError:
            try:
                self.root.attributes('-zoomed', True)
            except:
                self.root.geometry("1280x720")

        self.drives = {}
        self.queue = []
        self.photo_references = []
        self.is_processing = False
        self.active_tab = "audio"
        self.pulse_phase = 0.0
        self.current_progress = 0
        self.gradient_offset = 0
        self._banner_img_ref = None
        self._generate_gradient()

        self._build_ui()
        self.scan_usb()
        self.switch_tab("audio")
        self.root.after(40, self._animate)


    def _build_ui(self):
        style = ttk.Style()
        try: style.theme_use('clam')
        except: pass
        style.configure("App.TCombobox",
                        fieldbackground=SURFACE2, background=SURFACE2,
                        foreground=TEXT, selectforeground=TEXT,
                        selectbackground=SURFACE2, borderwidth=1,
                        arrowcolor=ACCENT, insertcolor=TEXT, relief="flat")
        style.map("App.TCombobox",
                  fieldbackground=[('readonly', SURFACE2)],
                  background=[('readonly', SURFACE2)])
        self.root.configure(bg=BG)

     #Banner
        self.banner_canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0, height=68)
        self.banner_canvas.pack(fill="x")

        right_bar = tk.Frame(self.banner_canvas, bg=BG)
        right_bar.place(relx=1.0, rely=0.5, anchor="e", x=-16)

        about_btn = self._flat_btn(right_bar, "☰", bg=SURFACE2, fg=TEXT, hover_bg=BORDER,
                                   command=self.show_about)
        about_btn.pack(side="right", padx=(8, 0))

        refresh_btn = self._flat_btn(right_bar, "⟳  Refresh", bg=SURFACE2, fg=TEXT,
                                     hover_bg=BORDER, command=self.scan_usb)
        refresh_btn.pack(side="right", padx=(8, 0))

        self.drive_combo = ttk.Combobox(right_bar, state="readonly", style="App.TCombobox",
                                        width=28, font=FONT_BODY)
        self.drive_combo.pack(side="right")

        drive_lbl = tk.Label(right_bar, text="Drive:", font=FONT_SMALL, fg=TEXT_DIM, bg=BG)
        drive_lbl.pack(side="right", padx=(0, 6))

        self.accent_line = tk.Frame(self.root, bg=ACCENT, height=2)
        self.accent_line.pack(fill="x")

        # Body
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=16, pady=12)

        left = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        tab_row = tk.Frame(left, bg=BG)
        tab_row.pack(fill="x", pady=(0, 8))

        self._tab_btns = {}
        for tab_id, label in [("audio", "🎵  Music"), ("video", "🎬  Video"), ("playlist", "🎶  Playlist")]:
            btn = self._tab_button(tab_row, label, tab_id)
            btn.pack(side="left", padx=(0, 6))
            self._tab_btns[tab_id] = btn

        self.tab_container = tk.Frame(left, bg=BG)
        self.tab_container.pack(fill="both", expand=True)

        self.tab_music    = tk.Frame(self.tab_container, bg=BG)
        self.tab_video    = tk.Frame(self.tab_container, bg=BG)
        self.tab_playlist = tk.Frame(self.tab_container, bg=BG)

        self.setup_tab(self.tab_music,    "audio")
        self.setup_tab(self.tab_video,    "video")
        self.setup_tab(self.tab_playlist, "playlist")

        # Right column (queue + log)
        right = tk.Frame(body, bg=BG, width=380)
        right.pack(side="right", fill="both", padx=(8, 0))
        right.pack_propagate(False)

        q_hdr = tk.Frame(right, bg=BG)
        q_hdr.pack(fill="x", pady=(0, 6))

        q_title = tk.Label(q_hdr, text="Transfer Queue", font=("Segoe UI", 11, "bold"),
                           fg=TEXT, bg=BG)
        q_title.pack(side="left")

        clr = self._flat_btn(q_hdr, "Clear All", bg=SURFACE2, fg=TEXT_DIM, hover_bg=ERROR,
                             command=self.clear_queue, font=("Segoe UI", 8, "bold"))
        clr.pack(side="right")

        q_outer = tk.Frame(right, bg=BORDER, padx=1, pady=1)
        q_outer.pack(fill="both", expand=True, pady=(0, 8))

        self.queue_canvas = tk.Canvas(q_outer, bg=SURFACE, highlightthickness=0)
        q_scroll = tk.Scrollbar(q_outer, orient="vertical", command=self.queue_canvas.yview)
        self.queue_frame = tk.Frame(self.queue_canvas, bg=SURFACE)
        self._q_win = self.queue_canvas.create_window((0, 0), window=self.queue_frame, anchor="nw")
        self.queue_canvas.bind("<Configure>", lambda e: self.queue_canvas.itemconfig(self._q_win, width=e.width))
        self.queue_canvas.configure(yscrollcommand=q_scroll.set)
        self.queue_canvas.pack(side="left", fill="both", expand=True)
        q_scroll.pack(side="right", fill="y")
        self._bind_scroll(self.queue_canvas, self.queue_frame)

        # Log
        log_outer = tk.Frame(right, bg=BORDER, padx=1, pady=1, height=180)
        log_outer.pack(fill="x")
        log_outer.pack_propagate(False)

        log_label = tk.Frame(log_outer, bg=SURFACE2, height=22)
        log_label.pack(fill="x")
        log_lbl_txt = tk.Label(log_label, text=" ◉  Activity Log",
                               font=("Segoe UI", 8, "bold"), fg=ACCENT, bg=SURFACE2)
        log_lbl_txt.pack(side="left", padx=6, pady=2)

        self.log_text = tk.Text(log_outer, bg=SURFACE, fg=TEXT_DIM, font=FONT_MONO,
                                state="disabled", wrap="word", insertbackground=ACCENT,
                                selectbackground=ACCENT2, borderwidth=0)
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

        # Footer 
        footer = tk.Frame(self.root, bg=SURFACE, height=80)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        border_line = tk.Frame(footer, bg=BORDER, height=1)
        border_line.pack(fill="x")

        inner_footer = tk.Frame(footer, bg=SURFACE)
        inner_footer.pack(fill="both", expand=True, padx=16, pady=8)

        prog_area = tk.Frame(inner_footer, bg=SURFACE)
        prog_area.pack(side="left", fill="both", expand=True, padx=(0, 16))

        self._prog_label = tk.Label(prog_area, text="Ready", font=("Segoe UI", 9),
                                    fg=TEXT_DIM, bg=SURFACE, anchor="w")
        self._prog_label.pack(fill="x")

        self.progress_canvas = tk.Canvas(prog_area, bg=SURFACE, highlightthickness=0, height=12)
        self.progress_canvas.pack(fill="x", pady=(6, 0))
        self.progress_canvas.bind("<Configure>", lambda e: self._draw_progress())

        self.send_btn = self._accent_button(inner_footer, "⬆  SEND QUEUE TO PSP",
                                            width=220, height=50,
                                            command=lambda: self.process_queue() if not self.is_processing else None)
        self.send_btn.pack(side="right")


    def _flat_btn(self, parent, text, width=None, height=32, bg=None, fg=None,
                  hover_bg=None, command=None, font=None):
        bg = bg or SURFACE2
        fg = fg or TEXT
        hover_bg = hover_bg or BORDER
        f = font or FONT_BTN
        btn = tk.Label(parent, text=text, font=f, fg=fg, bg=bg,
                       anchor="center", cursor="hand2", padx=10, pady=4)
        btn._bg = bg
        btn._hbg = hover_bg
        btn.bind("<Enter>", lambda e: btn.config(bg=btn._hbg))
        btn.bind("<Leave>", lambda e: btn.config(bg=btn._bg))
        if command:
            btn.bind("<Button-1>", lambda e: command())
        return btn

    def _tab_button(self, parent, text, tab_id):
        btn = tk.Label(parent, text=text, font=FONT_TAB,
                       fg=TEXT_DIM, bg=SURFACE2, padx=16, pady=8, cursor="hand2")
        btn.bind("<Button-1>", lambda e: self.switch_tab(tab_id))
        btn.bind("<Enter>", lambda e: btn.config(fg=TEXT) if self.active_tab != tab_id else None)
        btn.bind("<Leave>", lambda e: btn.config(fg=TEXT_DIM) if self.active_tab != tab_id else None)
        return btn

    def _accent_button(self, parent, text, width=180, height=44, command=None):
        canvas = tk.Canvas(parent, bg=SURFACE, highlightthickness=0,
                           width=width, height=height, cursor="hand2")
        canvas._text = text
        canvas._state = "normal"
        self._draw_accent_btn(canvas, width, height, text)
        if command:
            canvas.bind("<Button-1>", lambda e: command())
        canvas.bind("<Enter>",  lambda e: self._draw_accent_btn(canvas, width, height, canvas._text, hover=True))
        canvas.bind("<Leave>",  lambda e: self._draw_accent_btn(canvas, width, height, canvas._text, hover=False))
        return canvas

    def _draw_accent_btn(self, canvas, w, h, text, hover=False):
        canvas.delete("all")
        state = getattr(canvas, '_state', 'normal')
        if state == "disabled":
            fill = SURFACE2; txt_color = TEXT_DIM
        elif state == "processing":
            fill = WARN; txt_color = "#000000"
        elif hover:
            fill = ACCENT2; txt_color = "#ffffff"
        else:
            fill = ACCENT; txt_color = "#ffffff"
        self._rrect(canvas, 0, 0, w, h, 8, fill)
        canvas.create_text(w//2, h//2, text=text, font=("Segoe UI", 11, "bold"),
                           fill=txt_color, anchor="center")

    def _rrect(self, canvas, x0, y0, x1, y1, r, color, outline=""):
        canvas.create_arc(x0, y0, x0+r*2, y0+r*2, start=90,  extent=90, fill=color, outline=outline)
        canvas.create_arc(x1-r*2, y0, x1, y0+r*2, start=0,   extent=90, fill=color, outline=outline)
        canvas.create_arc(x0, y1-r*2, x0+r*2, y1, start=180, extent=90, fill=color, outline=outline)
        canvas.create_arc(x1-r*2, y1-r*2, x1, y1, start=270, extent=90, fill=color, outline=outline)
        canvas.create_rectangle(x0+r, y0, x1-r, y1, fill=color, outline=outline)
        canvas.create_rectangle(x0, y0+r, x1, y1-r, fill=color, outline=outline)



    def switch_tab(self, tab_id):
        self.active_tab = tab_id
        for frame in [self.tab_music, self.tab_video, self.tab_playlist]:
            frame.pack_forget()
        {"audio": self.tab_music, "video": self.tab_video,
         "playlist": self.tab_playlist}[tab_id].pack(fill="both", expand=True)
        for tid, btn in self._tab_btns.items():
            if tid == tab_id:
                btn.config(bg=ACCENT, fg="#ffffff")
            else:
                btn.config(bg=SURFACE2, fg=TEXT_DIM)

    def setup_tab(self, parent, media_type):
        search_row = tk.Frame(parent, bg=BG)
        search_row.pack(fill="x", pady=(0, 8))

        search_frame = tk.Frame(search_row, bg=SURFACE2,
                                highlightbackground=BORDER, highlightthickness=1)
        search_frame.pack(side="left", fill="x", expand=True)

        si = tk.Label(search_frame, text="🔍", font=("Segoe UI", 11),
                      fg=TEXT_DIM, bg=SURFACE2, padx=8)
        si.pack(side="left")

        search_var = tk.StringVar()
        entry = tk.Entry(search_frame, textvariable=search_var, fg=TEXT_DIM,
                         font=FONT_BODY, borderwidth=0, relief="flat",
                         bg=SURFACE2, insertbackground=TEXT, width=40)
        entry.pack(side="left", fill="both", expand=True, ipady=9)
        entry.insert(0, "Search YouTube or paste URL…")
        entry.bind("<FocusIn>",  lambda e: self.clear_ph(entry))
        entry.bind("<FocusOut>", lambda e: self.add_ph(entry))
        entry.bind("<Return>",   lambda e: self.search(search_var.get(), parent, media_type))

        search_btn = self._flat_btn(search_row, "Search", bg=ACCENT, fg="#ffffff",
                                    hover_bg=ACCENT2,
                                    command=lambda: self.search(search_var.get(), parent, media_type),
                                    font=("Segoe UI", 10, "bold"))
        search_btn.pack(side="left", padx=(8, 0))

        if media_type != "playlist":
            btn_row = tk.Frame(parent, bg=BG)
            btn_row.pack(fill="x", pady=(0, 8))

            btn_text = "📁  Add Local Music" if media_type == "audio" else "📁  Add Local Video"
            local_btn = self._flat_btn(btn_row, btn_text, bg=SURFACE2, fg=TEXT,
                                       hover_bg=BORDER,
                                       command=lambda: self.add_local_file(media_type))
            local_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))

            mgr_text = "🗂  Manage Music" if media_type == "audio" else "🗂  Manage Videos"
            mgr_btn = self._flat_btn(btn_row, mgr_text, bg=SURFACE2, fg=ACCENT,
                                     hover_bg=BORDER,
                                     command=lambda mt=media_type: self.open_file_manager(mt),
                                     font=("Segoe UI", 9, "bold"))
            mgr_btn.pack(side="left", fill="x", expand=True)

        else:
            pl_btn_row = tk.Frame(parent, bg=BG)
            pl_btn_row.pack(fill="x", pady=(0, 8))

            pl_mgr_btn = self._flat_btn(pl_btn_row, "🎶  Manage Playlists", bg=SURFACE2,
                                        fg=ACCENT, hover_bg=BORDER,
                                        command=self.open_playlist_manager,
                                        font=("Segoe UI", 9, "bold"))
            pl_mgr_btn.pack(fill="x")

        results_outer = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
        results_outer.pack(fill="both", expand=True)

        results_canvas = tk.Canvas(results_outer, bg=SURFACE, highlightthickness=0)
        scroll = tk.Scrollbar(results_outer, orient="vertical", command=results_canvas.yview)
        results_frame = tk.Frame(results_canvas, bg=SURFACE)

        parent.res_window = results_canvas.create_window((0, 0), window=results_frame, anchor="nw")
        results_canvas.bind("<Configure>", lambda e, c=results_canvas, w=parent.res_window:
                            c.itemconfig(w, width=e.width))
        results_canvas.configure(yscrollcommand=scroll.set)
        results_canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        parent.results_canvas = results_canvas
        parent.results_frame  = results_frame
        parent.cached_results = []
        parent.render_index   = 0
        parent.load_more_btn  = None
        self._bind_scroll(results_canvas, results_frame)


    def _generate_gradient(self):
        size = 3000
        c1, c2 = (0, 0, 0), (0, 45, 110)
        base = Image.new('RGB', (size, 1))
        
        for x in range(size):
            blend = (math.sin(x * 6 * math.pi / size) + 1) / 2 
            px = tuple(int(c1[i] + (c2[i] - c1[i]) * blend) for i in range(3))
            base.putpixel((x, 0), px)
            
        try:
            resize_filter = Image.Resampling.LANCZOS
            rotate_filter = Image.Resampling.BICUBIC
        except AttributeError:
            resize_filter = Image.LANCZOS
            rotate_filter = Image.BICUBIC
            
        base = base.resize((size, size), resize_filter)
        self._master_gradient = base.rotate(25, resample=rotate_filter, expand=True)

    def _draw_banner(self):
        c = self.banner_canvas
        w, h = c.winfo_width(), c.winfo_height()
        if w < 10 or h < 10: return
        off = self.gradient_offset
        img = self._master_gradient.crop((off, off, off + w, off + h))
        mask = Image.new('L', (w, h), 255)
        img.putalpha(mask)
        photo = ImageTk.PhotoImage(img)
        self._banner_img_ref = photo
        c.delete("gradient")
        c.create_image(0, 0, anchor="nw", image=photo, tags="gradient")
        c.tag_lower("gradient")
        c.delete("banner_text", "banner_icon")
        if not hasattr(self, '_banner_icon'):
            self._banner_icon = None
            icon_path = get_resource_path("Icon.png")
            if os.path.exists(icon_path):
                try:
                    ico = Image.open(icon_path).resize((40, 40), Image.Resampling.LANCZOS)
                    self._banner_icon = ImageTk.PhotoImage(ico)
                    self.photo_references.append(self._banner_icon)
                except: pass
        tx = 20
        if self._banner_icon:
            c.create_image(20, h//2, anchor="w", image=self._banner_icon, tags="banner_icon")
            tx = 72
        
        c.create_text(tx, h//2, text="PSP Media Suite",
                      font=("Segoe UI", 20, "bold"), fill="#ffffff",
                      anchor="w", tags="banner_text")


    def _animate(self):
        self.pulse_phase = (self.pulse_phase + 0.08) % (2 * math.pi)
        self.gradient_offset = (self.gradient_offset + 1) % 1500
        self._draw_banner()
        if self.current_progress > 0:
            self._draw_progress()
        self.root.after(40, self._animate)

    def _pulse_color(self, base_hex, target_hex):
        t = (1 - math.cos(self.pulse_phase)) / 2
        def lerp(a, b): return int(a + (b - a) * t)
        r1,g1,b1 = int(base_hex[1:3],16), int(base_hex[3:5],16), int(base_hex[5:7],16)
        r2,g2,b2 = int(target_hex[1:3],16), int(target_hex[3:5],16), int(target_hex[5:7],16)
        return f"#{lerp(r1,r2):02x}{lerp(g1,g2):02x}{lerp(b1,b2):02x}"


    def _draw_progress(self):
        c = self.progress_canvas
        w, h = c.winfo_width(), c.winfo_height()
        c.delete("all")
        if w < 4: return
        r = h // 2
        self._rrect(c, 0, 0, w, h, r, SURFACE2)
        if self.current_progress > 0:
            fill_w = max(r*2, int(w * self.current_progress / 100))
            col = self._pulse_color(ACCENT, "#0055aa")
            self._rrect(c, 0, 0, fill_w, h, r, col)

    def update_progress(self, val=None):
        if val is not None:
            self.current_progress = val
            if val >= 100:
                self._prog_label.config(text="✔  Done", fg=SUCCESS)
                self.root.after(2000, lambda: self.update_progress(0))
            elif val == 0:
                self._prog_label.config(text="Ready", fg=TEXT_DIM)
            else:
                self._prog_label.config(text=f"Processing… {int(val)}%", fg=ACCENT)
        self._draw_progress()


    def write_log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"› {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")


    def scan_usb(self):
        self.drives = {}
        found = []
        for part in psutil.disk_partitions(all=True):
            try:
                if os.path.exists(os.path.join(part.mountpoint, "PSP")):
                    size = psutil.disk_usage(part.mountpoint).total / (1024**3)
                    name = f"{(os.path.basename(part.mountpoint) or part.mountpoint)} ({size:.1f} GB)"
                    self.drives[name] = part.mountpoint
                    found.append(name)
            except: continue
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
                    except: pass
        unique = list(dict.fromkeys(found))
        self.drive_combo['values'] = unique
        if unique:
            self.drive_combo.current(0)
            self.write_log(f"Found PSP drive: {unique[0]}")
        else:
            self.drive_combo.set("No PSP Drive Found")
            self.write_log("No PSP drive detected. Connect your PSP in USB mode.")

    def _get_drive_path(self):
        name = self.drive_combo.get()
        return self.drives.get(name)
        

    def _bind_scroll(self, canvas, frame):
        def _scroll(event):
            if sys.platform == "darwin":
                canvas.yview_scroll(int(-1 * event.delta), "units")
            elif event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
            else:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _scroll)
        canvas.bind_all("<Button-4>",   _scroll)
        canvas.bind_all("<Button-5>",   _scroll)

    def clear_ph(self, entry):
        if entry.get().startswith("Search YouTube"):
            entry.delete(0, tk.END)
            entry.config(fg=TEXT)

    def add_ph(self, entry):
        if not entry.get():
            entry.insert(0, "Search YouTube or paste URL…")
            entry.config(fg=TEXT_DIM)

    def format_time(self, seconds):
        if not seconds: return "??:??"
        try:
            s = int(seconds); m, s = divmod(s, 60); h, m = divmod(m, 60)
            return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
        except: return "??:??"

    def add_local_file(self, media_type):
        ft = ([("Audio Files", "*.mp3 *.ogg *.opus *.m4a *.wav")]
              if media_type == "audio" else [("Video Files", "*.mp4 *.mkv *.avi *.mov *.webm")])
        for path in filedialog.askopenfilenames(title=f"Select Local {media_type.capitalize()}", filetypes=ft):
            name_no_ext = os.path.splitext(os.path.basename(path))[0]
            self.add_to_queue({'title': f"(Local) {name_no_ext}", 'url': path,
                               'is_local': True, 'pil_image': None,
                               'formatted_time': 'Local', 'raw_thumb_url': None}, media_type)


    def search(self, q, parent, media_type):
        if not q or q.startswith("Search YouTube"): return
        for w in parent.results_frame.winfo_children(): w.destroy()
        parent.cached_results = []
        parent.render_index = 0
        self.update_progress(15)
        self.write_log(f"Searching: {q[:50]}…")
        threading.Thread(target=self._search_thread, args=(q, parent, media_type), daemon=True).start()

    def _search_thread(self, q, parent, media_type):
        opts = {'quiet': True, 'extract_flat': True}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                if q.startswith("http"):
                    info = ydl.extract_info(q, download=False)
                    if info.get('_type') == 'playlist':
                        parent.cached_results = [info]
                    elif 'entries' in info:
                        parent.cached_results = list(info['entries'])
                    else:
                        parent.cached_results = [info]
                else:
                    info = ydl.extract_info(f"ytsearch24:{q}", download=False)
                    parent.cached_results = list(info.get('entries', [info]))
            self.root.after(0, self.trigger_load_chunk, parent, media_type)
        except Exception as e:
            self.root.after(0, lambda: self.update_progress(0))
            self.root.after(0, lambda: self.write_log(f"Search failed: {e}"))

    def trigger_load_chunk(self, parent, media_type):
        if parent.load_more_btn:
            parent.load_more_btn.destroy()
            parent.load_more_btn = None
        self.update_progress(40)
        threading.Thread(target=self._load_chunk_thread, args=(parent, media_type), daemon=True).start()

    def _load_chunk_thread(self, parent, media_type):
        start = parent.render_index
        chunk = parent.cached_results[start:start + 8]
        for r in chunk:
            url = r.get('url') or r.get('webpage_url') or r.get('original_url')
            if not url:
                vid_id = str(r.get('id', ''))
                url = (f"https://www.youtube.com/playlist?list={vid_id}"
                       if r.get('_type') == 'playlist' or vid_id.startswith(('PL','OL','RD'))
                       else f"https://www.youtube.com/watch?v={vid_id}")
                if "watch?v=PL" in url or "watch?v=OL" in url:
                    url = url.replace("watch?v=", "playlist?list=")
            r['url'] = url
            thumb_url = r.get('thumbnail') or (r['thumbnails'][-1].get('url') if r.get('thumbnails') else None)
            r['raw_thumb_url'] = thumb_url
            r['pil_image'] = self.fetch_image_bytes(thumb_url) if thumb_url else None
            r['formatted_time'] = self.format_time(r.get('duration', 0))
        self.root.after(0, self.render_chunk, chunk, parent, media_type)

    def fetch_image_bytes(self, url):
        try:
            resp = requests.get(url, timeout=3)
            return Image.open(BytesIO(resp.content)).resize((80, 45))
        except: return None

    def render_chunk(self, chunk, parent, media_type):
        btn_map = {
            "audio":    ("+ Add Music",    ACCENT,       "#ffffff"),
            "video":    ("+ Add Video",    ACCENT2,      "#ffffff"),
            "playlist": ("+ Add Playlist", "#8b5cf6",    "#ffffff"), 
        }
        btn_text, btn_bg, btn_fg = btn_map[media_type]

        for item in chunk:
            if not item.get('url'): continue
            row = tk.Frame(parent.results_frame, bg=SURFACE, height=58)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)
            row.bind("<Enter>", lambda e, f=row: f.config(bg=SURFACE2))
            row.bind("<Leave>", lambda e, f=row: f.config(bg=SURFACE))

            thumb_lbl = tk.Label(row, bg=SURFACE, width=80, height=45)
            thumb_lbl.pack(side="left", padx=(8,6), pady=6)
            if item.get('pil_image'):
                photo = ImageTk.PhotoImage(item['pil_image'])
                self.photo_references.append(photo)
                thumb_lbl.config(image=photo); thumb_lbl.image = photo
            else:
                thumb_lbl.config(bg=SURFACE2, text="▶", fg=TEXT_DIM, font=("Segoe UI", 14))

            info_f = tk.Frame(row, bg=SURFACE)
            info_f.pack(side="left", fill="both", expand=True, pady=6)
            
            info_f.bind("<Enter>", lambda e, f=row: f.config(bg=SURFACE2))
            info_f.bind("<Leave>", lambda e, f=row: f.config(bg=SURFACE))

            tk.Label(info_f, text=item.get('title','Unknown')[:65], bg=SURFACE, fg=TEXT,
                     font=FONT_BODY, anchor="w").pack(fill="x")
            tk.Label(info_f, text=item['formatted_time'], bg=SURFACE, fg=TEXT_DIM,
                     font=FONT_SMALL, anchor="w").pack(fill="x")

            add_btn = tk.Canvas(row, bg=SURFACE, highlightthickness=0, width=120, height=35, cursor="hand2")
            add_btn.pack(side="right", padx=10)
            self._draw_accent_btn(add_btn, 120, 35, btn_text)
            
            add_btn.delete("all")
            self._rrect(add_btn, 0, 0, 120, 35, 6, btn_bg)
            add_btn.create_text(60, 17, text=btn_text, font=("Segoe UI", 9, "bold"), fill=btn_fg)

            add_btn.bind("<Button-1>", lambda e, i=item, mt=media_type: self.add_to_queue(i, mt))

        parent.render_index += 8
        if parent.render_index < len(parent.cached_results):
            lm = tk.Canvas(parent.results_frame, bg=SURFACE, highlightthickness=0, width=250, height=35, cursor="hand2")
            lm.pack(pady=10)
            
            lm.delete("all")
            self._rrect(lm, 0, 0, 250, 35, 6, SURFACE2)
            lm.create_text(125, 17, text="🔽 LOAD MORE", font=("Segoe UI", 9, "bold"), fill=TEXT)

            parent.load_more_btn = lm
            lm.bind("<Button-1>", lambda e: self.trigger_load_chunk(parent, media_type))

        self.root.update_idletasks()
        parent.results_canvas.configure(scrollregion=parent.results_canvas.bbox("all"))
        self.update_progress(100)

    

    def add_to_queue(self, item, media_type):
        now = time.time()
        if hasattr(self, '_last_add_url') and self._last_add_url == item['url']:
            if now - getattr(self, '_last_add_time', 0) < 0.6: return
        self._last_add_url = item['url']
        self._last_add_time = now

        icons = {"audio": "🎵", "video": "🎬", "playlist": "🎶"}
        icon = icons.get(media_type, "•")

        row = tk.Frame(self.queue_frame, bg=SURFACE2, height=60)
        row.pack(fill="x", pady=1)
        row.pack_propagate(False)

        thumb_area = tk.Frame(row, bg=SURFACE2, width=60, height=60)
        thumb_area.pack(side="left", padx=(6,4))
        thumb_area.pack_propagate(False)
        if item.get('pil_image'):
            photo = ImageTk.PhotoImage(item['pil_image'].resize((54,34)))
            self.photo_references.append(photo)
            tk.Label(thumb_area, image=photo, bg=SURFACE2).place(relx=.5, rely=.55, anchor="center")
        else:
            tk.Label(thumb_area, text=icon, font=("Segoe UI", 18), fg=TEXT_DIM,
                     bg=SURFACE2).place(relx=.5, rely=.55, anchor="center")

        info = tk.Frame(row, bg=SURFACE2)
        info.pack(side="left", fill="both", expand=True, pady=4)
        tk.Label(info, text=item['title'][:42], bg=SURFACE2, fg=TEXT,
                 font=("Segoe UI", 9), anchor="w").pack(fill="x")
        tk.Label(info, text=f"{icon}  {media_type.upper()}  ·  {item['formatted_time']}",
                 bg=SURFACE2, fg=TEXT_DIM, font=("Segoe UI", 8), anchor="w").pack(fill="x")

        status_canvas = tk.Canvas(row, bg=SURFACE2, width=28, height=28, highlightthickness=0)
        status_canvas.pack(side="right", padx=(4,6))
        self._draw_status(status_canvas, "pending")

        rm_btn = tk.Label(row, text="✕", font=("Segoe UI", 10), fg=TEXT_DIM,
                          bg=SURFACE2, cursor="hand2", padx=6)
        rm_btn.pack(side="right")
        rm_btn.bind("<Enter>", lambda e: rm_btn.config(fg=ERROR))
        rm_btn.bind("<Leave>", lambda e: rm_btn.config(fg=TEXT_DIM))

        q_data = {'status': 'pending', 'type': media_type, 'url': item['url'],
                  'title': item['title'], 'thumb': item.get('raw_thumb_url'),
                  'is_local': item.get('is_local', False),
                  'status_cvs': status_canvas, 'q_row': row}

        rm_btn.bind("<Button-1>", lambda e: (not self.is_processing) and self.remove_from_queue(row, q_data))
        self.queue.append(q_data)
        self.root.update_idletasks()
        self.queue_canvas.configure(scrollregion=self.queue_canvas.bbox("all"))
        self.write_log(f"Queued: {item['title'][:40]}")

    def _draw_status(self, canvas, status, text=""):
        canvas.delete("all")
        colors = {"pending": (SURFACE,TEXT_DIM,"·"), "processing": (WARN,"#000","⏳"),
                  "success": (SUCCESS,"#000","✓"), "error": (ERROR,"#fff","✕")}
        bg, fg, sym = colors.get(status, (SURFACE, TEXT_DIM, "·"))
        if text: sym = text
        self._rrect(canvas, 2, 2, 26, 26, 6, bg)
        canvas.create_text(14, 14, text=sym, fill=fg, font=("Segoe UI", 9, "bold"))

    def remove_from_queue(self, row_widget, q_data):
        row_widget.destroy()
        if q_data in self.queue: self.queue.remove(q_data)
        self.root.update_idletasks()
        self.queue_canvas.configure(scrollregion=self.queue_canvas.bbox("all"))

    def clear_queue(self):
        if self.is_processing: return
        for item in self.queue: item['q_row'].destroy()
        self.queue.clear()
        self.root.update_idletasks()
        self.queue_canvas.configure(scrollregion=self.queue_canvas.bbox("all"))

    def pulse_item(self, item, toggle=False):
        if item.get('status') != 'processing': return
        self._draw_status(item['status_cvs'], "processing", "⏳" if toggle else "↻")
        self.root.after(600, self.pulse_item, item, not toggle)

    def _set_send_btn(self, text, state="normal"):
        self.send_btn._text = text
        self.send_btn._state = state
        w = self.send_btn.winfo_width() or 220
        h = self.send_btn.winfo_height() or 50
        self._draw_accent_btn(self.send_btn, w, h, text)



    def open_file_manager(self, media_type):
        drive = self._get_drive_path()
        if not drive:
            messagebox.showwarning("No Drive", "Connect your PSP first.")
            return
        folder = os.path.join(drive, "MUSIC" if media_type == "audio" else "VIDEO")
        os.makedirs(folder, exist_ok=True)
        exts = (".mp3",".ogg",".opus",".m4a",".wav") if media_type=="audio" else (".mp4",".avi",".mkv",".mov")

        win = tk.Toplevel(self.root)
        win.title(f"Manage {'Music' if media_type=='audio' else 'Videos'} on PSP")
        win.geometry("680x520")
        win.configure(bg=BG)
        win.transient(self.root)
        win.wait_visibility()
        win.grab_set()

        tk.Frame(win, bg=ACCENT, height=3).pack(fill="x")

        hdr = tk.Frame(win, bg=BG)
        hdr.pack(fill="x", padx=16, pady=(12,6))
        icon = "🎵" if media_type == "audio" else "🎬"
        tk.Label(hdr, text=f"{icon}  {'Music' if media_type=='audio' else 'Video'} Files on PSP",
                 font=("Segoe UI", 13, "bold"), fg=TEXT, bg=BG).pack(side="left")
        tk.Label(hdr, text=folder, font=("Segoe UI", 8), fg=TEXT_DIM, bg=BG).pack(side="left", padx=(10,0), pady=(4,0))

        list_outer = tk.Frame(win, bg=BORDER, padx=1, pady=1)
        list_outer.pack(fill="both", expand=True, padx=16, pady=(0,8))

        cols = ("name", "size")
        tree = ttk.Treeview(list_outer, columns=cols, show="headings", selectmode="extended")
        tree.heading("name", text="File Name")
        tree.heading("size", text="Size")
        tree.column("name", width=480, anchor="w")
        tree.column("size", width=80, anchor="e")

        style = ttk.Style()
        style.configure("Manager.Treeview",
                        background=SURFACE, fieldbackground=SURFACE,
                        foreground=TEXT, rowheight=26, borderwidth=0)
        style.configure("Manager.Treeview.Heading",
                        background=SURFACE2, foreground=TEXT, borderwidth=0)
        style.map("Manager.Treeview", background=[("selected", ACCENT)],
                  foreground=[("selected", "#ffffff")])
        tree.configure(style="Manager.Treeview")

        vsb = ttk.Scrollbar(list_outer, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        def load_files():
            tree.delete(*tree.get_children())
            try:
                for f in sorted(os.listdir(folder)):
                    if f.lower().endswith(exts):
                        fp = os.path.join(folder, f)
                        try:
                            size_kb = os.path.getsize(fp) / 1024
                            size_str = f"{size_kb/1024:.1f} MB" if size_kb > 1024 else f"{size_kb:.0f} KB"
                            tree.insert("", tk.END, iid=f, values=(f, size_str))
                        except: pass
            except Exception as e:
                self.write_log(f"Manager error: {e}")
        load_files()

        btn_row = tk.Frame(win, bg=BG)
        btn_row.pack(fill="x", padx=16, pady=(0,12))

        def rename_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Select File", "Select a file to rename.", parent=win)
                return
            old_name = sel[0]
            ext = os.path.splitext(old_name)[1]
            old_base = os.path.splitext(old_name)[0]
            new_base = simpledialog.askstring("Rename", f"New name for:\n{old_name}",
                                              initialvalue=old_base, parent=win)
            if not new_base: return
            
            new_name = new_base.strip() + ext
            try:
                new_path = os.path.join(folder, new_name)
                os.rename(os.path.join(folder, old_name), new_path)
                
                if media_type == 'video':
                    old_thm = os.path.join(folder, old_base + ".thm")
                    new_thm = os.path.join(folder, new_base.strip() + ".thm")
                    if os.path.exists(old_thm):
                        try:
                            os.rename(old_thm, new_thm)
                        except: pass

                elif media_type == 'audio':
                    if ext.lower() == '.mp3':
                        try:
                            audio = MP3(new_path, ID3=ID3)
                            if audio.tags is None:
                                audio.add_tags()
                            audio.tags.add(TIT2(encoding=3, text=new_base.strip()))
                            audio.save(v2_version=3, v1=2)
                        except Exception as tag_err:
                            self.write_log(f"Warning: Could not update internal ID3 tag for {new_name}")
                            
                    pl_dir = os.path.join(drive, "PSP", "PLAYLIST", "MUSIC")
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
                                        self.write_log(f"Updated playlist reference in {pl_file}")
                                except Exception as pl_err:
                                    pass

                self.write_log(f"Renamed: {old_name} → {new_name}")
                load_files()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=win)

        def delete_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Select File", "Select file(s) to delete.", parent=win)
                return
            if not messagebox.askyesno("Confirm Delete",
                                       f"Delete {len(sel)} file(s)?\nThis cannot be undone.", parent=win):
                return
            for fname in sel:
                try:
                    os.remove(os.path.join(folder, fname))
                    self.write_log(f"Deleted: {fname}")
                except Exception as e:
                    messagebox.showerror("Error", str(e), parent=win)
            load_files()

        def open_folder():
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])

        for txt, cmd, col in [
            ("✏  Rename",      rename_selected, ACCENT),
            ("🗑  Delete",      delete_selected, ERROR),
            ("📂  Open Folder", open_folder,     SURFACE2),
            ("↩  Refresh",      load_files,      SURFACE2),
        ]:
            b = self._flat_btn(btn_row, txt, bg=col, fg="#ffffff" if col not in (SURFACE2,) else TEXT,
                               hover_bg=BORDER, command=cmd, font=("Segoe UI", 9, "bold"))
            b.pack(side="left", padx=(0, 8))

 

    def open_playlist_manager(self):
        drive = self._get_drive_path()
        if not drive:
            messagebox.showwarning("No Drive", "Connect your PSP first.")
            return

        music_dir   = os.path.join(drive, "MUSIC")
        pl_dir      = os.path.join(drive, "PSP", "PLAYLIST", "MUSIC")
        os.makedirs(music_dir, exist_ok=True)
        os.makedirs(pl_dir,    exist_ok=True)

        win = tk.Toplevel(self.root)
        win.title("Manage Playlists — PSP Media Suite")
        win.geometry("820x560")
        win.configure(bg=BG)
        win.transient(self.root)
        win.wait_visibility()
        win.grab_set()

        tk.Frame(win, bg=ACCENT, height=3).pack(fill="x")

        hdr = tk.Frame(win, bg=BG)
        hdr.pack(fill="x", padx=16, pady=(12, 8))
        tk.Label(hdr, text="🎶  Playlist Manager", font=("Segoe UI", 13, "bold"),
                 fg=TEXT, bg=BG).pack(side="left")

        panes = tk.Frame(win, bg=BG)
        panes.pack(fill="both", expand=True, padx=16, pady=(0,8))

        left_pane = tk.Frame(panes, bg=BG, width=240)
        left_pane.pack(side="left", fill="y", padx=(0, 10))
        left_pane.pack_propagate(False)

        tk.Label(left_pane, text="Playlists", font=("Segoe UI", 10, "bold"),
                 fg=TEXT, bg=BG).pack(anchor="w", pady=(0,4))

        pl_list_outer = tk.Frame(left_pane, bg=BORDER, padx=1, pady=1)
        pl_list_outer.pack(fill="both", expand=True)

        pl_listbox = tk.Listbox(pl_list_outer, bg=SURFACE, fg=TEXT, font=("Segoe UI", 10),
                                selectbackground=ACCENT,
                                selectforeground="#ffffff",
                                borderwidth=0, highlightthickness=0, activestyle="none")
        pl_scroll = ttk.Scrollbar(pl_list_outer, orient="vertical", command=pl_listbox.yview)
        pl_listbox.configure(yscrollcommand=pl_scroll.set)
        pl_listbox.pack(side="left", fill="both", expand=True)
        pl_scroll.pack(side="right", fill="y")

        pl_btn_row = tk.Frame(left_pane, bg=BG)
        pl_btn_row.pack(fill="x", pady=(6,0))

        right_pane = tk.Frame(panes, bg=BG)
        right_pane.pack(side="left", fill="both", expand=True)

        pl_name_var = tk.StringVar(value="← Select or create a playlist")
        tk.Label(right_pane, textvariable=pl_name_var, font=("Segoe UI", 10, "bold"),
                 fg=TEXT, bg=BG).pack(anchor="w", pady=(0,4))

        song_outer = tk.Frame(right_pane, bg=BORDER, padx=1, pady=1)
        song_outer.pack(fill="both", expand=True)

        song_listbox = tk.Listbox(song_outer, bg=SURFACE, fg=TEXT, font=("Segoe UI", 10),
                                  selectbackground=ACCENT,
                                  selectforeground="#ffffff",
                                  borderwidth=0, highlightthickness=0, activestyle="none",
                                  selectmode="extended")
        song_scroll = ttk.Scrollbar(song_outer, orient="vertical", command=song_listbox.yview)
        song_listbox.configure(yscrollcommand=song_scroll.set)
        song_listbox.pack(side="left", fill="both", expand=True)
        song_scroll.pack(side="right", fill="y")

        song_btn_row = tk.Frame(right_pane, bg=BG)
        song_btn_row.pack(fill="x", pady=(6,0))

        current_pl = {"name": None}   

        def _pl_path(name):
            return os.path.join(pl_dir, name + ".m3u8")

        def _read_pl(name):
            path = _pl_path(name)
            if not os.path.exists(path): return []
            with open(path, "r", encoding="utf-8") as f:
                return [l.strip() for l in f if l.strip()]

        def _write_pl(name, lines):
            with open(_pl_path(name), "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

        def _song_display(raw_line):
            """Convert \MUSIC\filename.mp3 → filename.mp3 for display."""
            return os.path.basename(raw_line.replace("\\", "/"))

        def load_playlists():
            pl_listbox.delete(0, tk.END)
            try:
                for f in sorted(os.listdir(pl_dir)):
                    if f.lower().endswith(".m3u8"):
                        pl_listbox.insert(tk.END, os.path.splitext(f)[0])
            except Exception as e:
                self.write_log(f"Load playlist error: {e}")

        def on_pl_select(event=None):
            sel = pl_listbox.curselection()
            if not sel: return
            name = pl_listbox.get(sel[0])
            current_pl["name"] = name
            pl_name_var.set(f"Songs in: {name}")
            load_songs()

        pl_listbox.bind("<<ListboxSelect>>", on_pl_select)

        def load_songs():
            song_listbox.delete(0, tk.END)
            if not current_pl["name"]: return
            for line in _read_pl(current_pl["name"]):
                song_listbox.insert(tk.END, _song_display(line))

        def new_playlist():
            name = simpledialog.askstring("New Playlist", "Playlist name:", parent=win)
            if not name: return
            name = name.strip()
            if os.path.exists(_pl_path(name)):
                messagebox.showwarning("Exists", f"'{name}' already exists.", parent=win)
                return
            _write_pl(name, [])
            self.write_log(f"Created playlist: {name}")
            load_playlists()

        def rename_playlist():
            if not current_pl["name"]:
                messagebox.showinfo("Select", "Select a playlist first.", parent=win)
                return
            old = current_pl["name"]
            new = simpledialog.askstring("Rename", "New name:", initialvalue=old, parent=win)
            if not new: return
            new = new.strip()
            try:
                os.rename(_pl_path(old), _pl_path(new))
                current_pl["name"] = new
                pl_name_var.set(f"Songs in: {new}")
                self.write_log(f"Renamed playlist: {old} → {new}")
                load_playlists()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=win)

        def delete_playlist():
            if not current_pl["name"]:
                messagebox.showinfo("Select", "Select a playlist first.", parent=win)
                return
            if not messagebox.askyesno("Delete", f"Delete playlist '{current_pl['name']}'?", parent=win):
                return
            try:
                os.remove(_pl_path(current_pl["name"]))
                self.write_log(f"Deleted playlist: {current_pl['name']}")
                current_pl["name"] = None
                pl_name_var.set("← Select or create a playlist")
                song_listbox.delete(0, tk.END)
                load_playlists()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=win)

        for txt, cmd, col in [
            ("＋ New",    new_playlist,    ACCENT),
            ("✏ Rename", rename_playlist, SURFACE2),
            ("🗑 Delete", delete_playlist, ERROR),
        ]:
            b = self._flat_btn(pl_btn_row, txt, bg=col,
                               fg="#ffffff" if col != SURFACE2 else TEXT,
                               hover_bg=BORDER, command=cmd, font=("Segoe UI", 9, "bold"))
            b.pack(side="top", fill="x", pady=3)

        def add_songs():
            if not current_pl["name"]:
                messagebox.showinfo("Select Playlist", "Select a playlist first.", parent=win)
                return
            try:
                avail = [f for f in sorted(os.listdir(music_dir)) if f.lower().endswith(".mp3")]
            except:
                avail = []
            if not avail:
                messagebox.showinfo("No Music", "No .mp3 files found in PSP MUSIC folder.", parent=win)
                return

            pick = tk.Toplevel(win)
            pick.title("Add Songs")
            pick.geometry("460x400")
            pick.configure(bg=BG)
            pick.transient(win)
            pick.wait_visibility()
            pick.grab_set()

            tk.Label(pick, text="Select songs to add:", font=("Segoe UI", 10, "bold"),
                     fg=TEXT, bg=BG).pack(padx=16, pady=(12,4), anchor="w")

            pick_outer = tk.Frame(pick, bg=BORDER, padx=1, pady=1)
            pick_outer.pack(fill="both", expand=True, padx=16, pady=(0,8))

            pick_lb = tk.Listbox(pick_outer, bg=SURFACE, fg=TEXT, font=("Segoe UI", 10),
                                 selectbackground=ACCENT,
                                 selectforeground="#ffffff",
                                 borderwidth=0, highlightthickness=0,
                                 activestyle="none", selectmode="extended")
            pick_sb = ttk.Scrollbar(pick_outer, orient="vertical", command=pick_lb.yview)
            pick_lb.configure(yscrollcommand=pick_sb.set)
            pick_lb.pack(side="left", fill="both", expand=True)
            pick_sb.pack(side="right", fill="y")

            existing = _read_pl(current_pl["name"])
            existing_files = {os.path.basename(l.replace("\\","/")).lower() for l in existing}
            for f in avail:
                if f.lower() not in existing_files:
                    pick_lb.insert(tk.END, f)

            def confirm_add():
                sel = pick_lb.curselection()
                if not sel: pick.destroy(); return
                lines = _read_pl(current_pl["name"])
                for idx in sel:
                    fname = pick_lb.get(idx)
                    lines.append(f"\\MUSIC\\{fname}")
                    self.write_log(f"Added to {current_pl['name']}: {fname}")
                _write_pl(current_pl["name"], lines)
                load_songs()
                pick.destroy()

            add_row = tk.Frame(pick, bg=BG)
            add_row.pack(fill="x", padx=16, pady=(0,12))
            self._flat_btn(add_row, "✚  Add Selected", bg=ACCENT,
                           fg="#ffffff", hover_bg=ACCENT2,
                           command=confirm_add, font=("Segoe UI", 10, "bold")).pack(side="left")
            self._flat_btn(add_row, "Cancel", bg=SURFACE2, fg=TEXT,
                           hover_bg=BORDER, command=pick.destroy).pack(side="left", padx=(8,0))

        def remove_songs():
            if not current_pl["name"]:
                messagebox.showinfo("Select Playlist", "Select a playlist first.", parent=win)
                return
            sel = song_listbox.curselection()
            if not sel:
                messagebox.showinfo("Select", "Select songs to remove.", parent=win)
                return
            lines = _read_pl(current_pl["name"])
            to_remove = {song_listbox.get(i).lower() for i in sel}
            new_lines = [l for l in lines if _song_display(l).lower() not in to_remove]
            _write_pl(current_pl["name"], new_lines)
            self.write_log(f"Removed {len(sel)} song(s) from {current_pl['name']}")
            load_songs()

        def move_up():
            sel = song_listbox.curselection()
            if not sel or sel[0] == 0: return
            lines = _read_pl(current_pl["name"])
            for i in sel:
                if i > 0:
                    lines[i-1], lines[i] = lines[i], lines[i-1]
            _write_pl(current_pl["name"], lines)
            load_songs()
            song_listbox.selection_set([i-1 for i in sel if i > 0])

        def move_down():
            sel = song_listbox.curselection()
            if not sel or sel[-1] == song_listbox.size()-1: return
            lines = _read_pl(current_pl["name"])
            for i in reversed(sel):
                if i < len(lines)-1:
                    lines[i], lines[i+1] = lines[i+1], lines[i]
            _write_pl(current_pl["name"], lines)
            load_songs()
            song_listbox.selection_set([i+1 for i in sel if i < len(lines)-1])

        for txt, cmd, col in [
            ("✚ Add Songs",    add_songs,    ACCENT),
            ("✕ Remove",       remove_songs, ERROR),
            ("▲ Move Up",      move_up,      SURFACE2),
            ("▼ Move Down",    move_down,    SURFACE2),
        ]:
            b = self._flat_btn(song_btn_row, txt, bg=col,
                               fg="#ffffff" if col not in (SURFACE2,) else TEXT,
                               hover_bg=BORDER, command=cmd, font=("Segoe UI", 9, "bold"))
            b.pack(side="left", padx=(0, 6))

        load_playlists()


    def show_about(self):
        about = tk.Toplevel(self.root)
        about.title("Menu")
        about.geometry("300x420")
        about.configure(bg=SURFACE)
        about.resizable(False, False)

        tk.Frame(about, bg=ACCENT, height=3).pack(fill="x")
        inner = tk.Frame(about, bg=SURFACE)
        inner.pack(fill="both", expand=True, padx=24, pady=20)

        icon_path = get_resource_path("Icon.png")
        if os.path.exists(icon_path):
            try:
                img = Image.open(icon_path).resize((72, 72), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                lbl = tk.Label(inner, image=photo, bg=SURFACE)
                lbl.image = photo
                lbl.pack(pady=(0, 12))
            except: pass

        tk.Label(inner, text="PSP Media Suite", font=("Segoe UI", 14, "bold"),
                 fg=TEXT, bg=SURFACE).pack()
        tk.Label(inner, text="by vmg265  ·  v1.6", font=("Segoe UI", 9),
                 fg=TEXT_DIM, bg=SURFACE).pack(pady=(4, 16))

        for label, url in [("⭐  GitHub", "https://github.com/vmg265/PSP-Media-Suite"),
                            ("☕  Buy me a tea", "https://rzp.io/rzp/pFrhgY8")]:
            b = self._flat_btn(inner, label, bg=SURFACE2, fg=TEXT, hover_bg=BORDER,
                               command=lambda u=url: webbrowser.open(u),
                               font=("Segoe UI", 10))
            b.pack(fill="x", pady=3)

        self._flat_btn(inner, "🔧  Troubleshooter", bg=SURFACE2, fg=ACCENT,
                       hover_bg=BORDER, command=self.show_troubleshooter,
                       font=("Segoe UI", 10)).pack(fill="x", pady=(12, 0))

    def show_troubleshooter(self):
        win = tk.Toplevel(self.root)
        win.title("Troubleshooter")
        win.geometry("600x420")
        win.configure(bg=SURFACE)
        tk.Frame(win, bg=ACCENT, height=2).pack(fill="x")
        txt = tk.Text(win, wrap="word", bg=SURFACE, fg=TEXT, font=FONT_MONO,
                      padx=12, pady=12, insertbackground=ACCENT, selectbackground=ACCENT2, borderwidth=0)
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        ts_path = get_resource_path("troubleshooter_box.txt")
        if os.path.exists(ts_path):
            try:
                with open(ts_path, "r", encoding="utf-8") as f:
                    txt.insert(tk.END, f.read())
            except Exception as e:
                txt.insert(tk.END, f"Error reading file: {e}")
        else:
            txt.insert(tk.END, "troubleshooter_box.txt not found.\nEnsure it is in the same directory.")
        txt.config(state="disabled")


    def process_queue(self):
        drive_name = self.drive_combo.get()
        if drive_name not in self.drives:
            messagebox.showwarning("No Drive", "Please select a valid PSP drive first.")
            return
        if not self.queue:
            messagebox.showinfo("Queue Empty", "Add some items to the queue first.")
            return
        self.is_processing = True
        self._set_send_btn("⏳  PROCESSING…", "processing")
        threading.Thread(target=self._process_queue,
                         args=(self.drives[drive_name],), daemon=True).start()

    def _process_queue(self, drive_path):
        ff_path = get_resource_path("ffmpeg" if os.name != 'nt' else "ffmpeg.exe")
        total = len(self.queue)
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        for i, item in enumerate(self.queue):
            if item['status'] == 'success': continue
            self.root.after(0, lambda v=(i / total) * 100: self.update_progress(v))
            self.root.after(0, lambda msg=f"Processing: {item['title'][:40]}": self.write_log(msg))
            clean_title = os.path.splitext(item['title'])[0] if item.get('is_local') else item['title']
            clean_name  = "".join(x for x in clean_title if x.isalnum() or x in " .-_")[:100]
            item['status'] = 'processing'
            self.root.after(0, self.pulse_item, item)

            for f in os.listdir("."):
                if f.startswith("temp.") or f.startswith("temp_raw.") or f in ("temp_thumb.jpg", "cover.jpg"):
                    try: os.remove(f)
                    except: pass
            try:
                if item['type'] == 'playlist':
                    target_dir   = os.path.join(drive_path, "MUSIC")
                    playlist_dir = os.path.join(drive_path, "PSP", "PLAYLIST", "MUSIC")
                    os.makedirs(target_dir, exist_ok=True)
                    os.makedirs(playlist_dir, exist_ok=True)
                    clean_pl = "".join(x for x in item['title'] if x.isalnum() or x in " .-_")[:100]
                    m3u8_lines = []
                    with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                        info_dict = ydl.extract_info(item['url'], download=False)
                        entries   = info_dict.get('entries', [info_dict])
                    for ei, entry in enumerate(entries):
                        if not entry: continue
                        entry_url   = entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
                        entry_title = entry.get('title', f"Track {ei+1}")
                        clean_en    = "".join(x for x in entry_title if x.isalnum() or x in " .-_")[:100]
                        self.root.after(0, lambda t=entry_title: self.write_log(f"  ↳ {t[:30]}"))
                        dl_opts = {
                            'format': 'bestaudio/best', 'ffmpeg_location': ff_path,
                            'outtmpl': 'temp_raw.%(ext)s', 'nopart': True, 'continuedl': False,
                            'postprocessors': [{'key': 'FFmpegExtractAudio',
                                               'preferredcodec': 'mp3', 'preferredquality': '192'}],
                            'postprocessor_args': ['-map_metadata', '-1']
                        }
                        try:
                            with yt_dlp.YoutubeDL(dl_opts) as ydl2:
                                einfo = ydl2.extract_info(entry_url, download=True)
                            img = self._get_best_thumbnail(einfo, entry.get('thumbnail'))
                            if img:
                                try:
                                    w2, h2 = img.size; s = min(w2, h2)
                                    img = img.crop(((w2-s)//2, (h2-s)//2, (w2+s)//2, (h2+s)//2))
                                    img = img.resize((600, 600), Image.Resampling.LANCZOS)
                                    img.convert('RGB').save("cover.jpg", "JPEG", quality=85)
                                except: pass
                            audio = MP3("temp_raw.mp3", ID3=ID3)
                            if audio.tags is None: audio.add_tags()
                            else: audio.tags.clear()
                            audio.tags.add(TIT2(encoding=3, text=entry_title))
                            audio.tags.add(TPE1(encoding=3, text="YouTube Audio"))
                            audio.tags.add(TALB(encoding=3, text=item['title']))
                            if os.path.exists("cover.jpg"):
                                with open("cover.jpg", "rb") as af:
                                    audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3,
                                                        desc='Cover', data=af.read()))
                            audio.save(v2_version=3, v1=2)
                            shutil.move("temp_raw.mp3", os.path.join(target_dir, clean_en + ".mp3"))
                            m3u8_lines.append(f"\\MUSIC\\{clean_en}.mp3")
                        except Exception as e:
                            self.root.after(0, lambda err=str(e): self.write_log(f"  ✕ Entry failed: {err[:40]}"))
                        for f in os.listdir("."):
                            if f.startswith("temp.") or f.startswith("temp_raw.") or f in ("temp_thumb.jpg", "cover.jpg"):
                                try: os.remove(f)
                                except: pass
                    if m3u8_lines:
                        with open(os.path.join(playlist_dir, clean_pl + ".m3u8"), "w", encoding="utf-8") as f:
                            f.write("\n".join(m3u8_lines))
                    item['status'] = 'success'
                    self.root.after(0, lambda i=item: self._draw_status(i['status_cvs'], "success"))

                elif item['type'] == 'audio':
                    target_dir = os.path.join(drive_path, "MUSIC")
                    os.makedirs(target_dir, exist_ok=True)
                    if item.get('is_local'):
                        subprocess.run([ff_path, "-y", "-i", item['url'],
                                        "-vn", "-ar", "44100", "-ac", "2", "-b:a", "192k", "temp_raw.mp3"],
                                       startupinfo=startupinfo)
                    else:
                        opts = {
                            'format': 'bestaudio/best', 'ffmpeg_location': ff_path,
                            'outtmpl': 'temp_raw.%(ext)s', 'nopart': True, 'continuedl': False,
                            'postprocessors': [{'key': 'FFmpegExtractAudio',
                                               'preferredcodec': 'mp3', 'preferredquality': '192'}],
                            'postprocessor_args': ['-map_metadata', '-1']
                        }
                        with yt_dlp.YoutubeDL(opts) as ydl:
                            info_dict = ydl.extract_info(item['url'], download=True)
                        img = self._get_best_thumbnail(info_dict, item.get('thumb'))
                        if img:
                            try:
                                w2, h2 = img.size; s = min(w2, h2)
                                img = img.crop(((w2-s)//2, (h2-s)//2, (w2+s)//2, (h2+s)//2))
                                img = img.resize((600, 600), Image.Resampling.LANCZOS)
                                img.convert('RGB').save("cover.jpg", "JPEG", quality=85)
                            except: pass
                    audio = MP3("temp_raw.mp3", ID3=ID3)
                    if audio.tags is None: audio.add_tags()
                    else: audio.tags.clear()
                    audio.tags.add(TIT2(encoding=3, text=item["title"]))
                    audio.tags.add(TPE1(encoding=3, text="YouTube Audio" if not item.get('is_local') else "Local Audio"))
                    audio.tags.add(TALB(encoding=3, text="PSP Media Suite"))
                    if os.path.exists("cover.jpg"):
                        with open("cover.jpg", "rb") as af:
                            audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3,
                                                desc='Cover', data=af.read()))
                    audio.save(v2_version=3, v1=2)
                    shutil.move("temp_raw.mp3", os.path.join(target_dir, clean_name + ".mp3"))
                    item['status'] = 'success'
                    self.root.after(0, lambda i=item: self._draw_status(i['status_cvs'], "success"))

                else:  
                    target_dir = os.path.join(drive_path, "VIDEO")
                    os.makedirs(target_dir, exist_ok=True)
                    if item.get('is_local'):
                        subprocess.run([ff_path, "-y", "-i", item['url'],
                                        "-c:v", "libx264", "-profile:v", "baseline", "-level", "3.0",
                                        "-pix_fmt", "yuv420p", "-vf", "scale=480:272",
                                        "-b:v", "768k", "-c:a", "aac", "-b:a", "128k",
                                        "-ar", "48000", "temp.mp4"], startupinfo=startupinfo)
                        try:
                            subprocess.run([ff_path, "-y", "-i", item['url'],
                                            "-ss", "00:00:01", "-vframes", "1", "temp_thumb.jpg"],
                                           startupinfo=startupinfo)
                            if os.path.exists("temp_thumb.jpg"):
                                img = Image.open("temp_thumb.jpg")
                        except: pass
                    else:
                        opts = {
                            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                            'ffmpeg_location': ff_path, 'outtmpl': 'temp_raw.%(ext)s',
                            'nopart': True, 'continuedl': False
                        }
                        with yt_dlp.YoutubeDL(opts) as ydl:
                            info_dict = ydl.extract_info(item['url'], download=True)
                        img = self._get_best_thumbnail(info_dict, item.get('thumb'))
                        raw_file = next((f for f in os.listdir(".")
                                         if f.startswith("temp_raw.") and not f.endswith(".mp3")), None)
                        if raw_file:
                            self.root.after(0, lambda: self.write_log("Converting to PSP format (H.264 480×272)…"))
                            subprocess.run([ff_path, "-y", "-i", raw_file,
                                            "-c:v", "libx264", "-profile:v", "baseline", "-level", "3.0",
                                            "-pix_fmt", "yuv420p", "-vf", "scale=480:272",
                                            "-b:v", "768k", "-c:a", "aac", "-b:a", "128k",
                                            "-ar", "48000", "temp.mp4"], startupinfo=startupinfo)
                    if 'img' in locals() and img:
                        try:
                            w2, h2 = img.size; target_ratio = 160 / 120.0
                            if w2 / h2 > target_ratio:
                                nw = int(target_ratio * h2)
                                img = img.crop(((w2-nw)//2, 0, (w2+nw)//2, h2))
                            else:
                                nh = int(w2 / target_ratio)
                                img = img.crop((0, (h2-nh)//2, w2, (h2+nh)//2))
                            img = img.resize((160, 120), Image.Resampling.LANCZOS)
                            img.convert('RGB').save(os.path.join(target_dir, clean_name + ".thm"), "JPEG")
                        except Exception as e:
                            self.root.after(0, lambda err=str(e): self.write_log(f".THM Error: {err[:40]}"))
                    shutil.move("temp.mp4", os.path.join(target_dir, clean_name + ".mp4"))
                    item['status'] = 'success'
                    self.root.after(0, lambda i=item: self._draw_status(i['status_cvs'], "success"))

            except Exception as e:
                self.write_log(f"Error: {e}")
                item['status'] = 'error'
                self.root.after(0, lambda i=item: self._draw_status(i['status_cvs'], "error"))

            for f in os.listdir("."):
                if f.startswith("temp.") or f.startswith("temp_raw.") or f in ("temp_thumb.jpg", "cover.jpg"):
                    try: os.remove(f)
                    except: pass
            if 'img' in dir(): del img

        self.is_processing = False
        self.root.after(0, lambda: self.update_progress(100))
        self.root.after(0, lambda: self._set_send_btn("⬆  SEND QUEUE TO PSP", "normal"))
        self.root.after(0, lambda: self.write_log("✔ All done! Check queue for statuses."))
        self.root.after(0, lambda: messagebox.showinfo("Done!", "All items processed. Check the queue for statuses."))


    def _get_best_thumbnail(self, info_dict, fallback_url):
        urls = []
        if info_dict and info_dict.get('thumbnails'):
            for t in reversed(info_dict['thumbnails']):
                if t.get('url'): urls.append(t['url'])
        if info_dict and info_dict.get('thumbnail'):
            urls.append(info_dict['thumbnail'])
        if fallback_url:
            urls.append(fallback_url)
        for u in urls:
            if not u.startswith("http"): continue
            try:
                r = requests.get(u, timeout=5)
                if r.status_code == 200:
                    try:
                        img = Image.open(BytesIO(r.content))
                        img.verify()
                        return Image.open(BytesIO(r.content))
                    except: pass
            except: pass
        return None


if __name__ == "__main__":
    root = tk.Tk()
    app = PSPMediaSuite(root)
    root.mainloop()
