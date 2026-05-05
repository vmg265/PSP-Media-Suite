import os, sys, shutil, threading, psutil, requests, subprocess, webbrowser, time, math, tkinter as tk
from tkinter import messagebox, ttk, filedialog
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
        self.root.title("PSP Media Suite v1.5")
        
        try:
            self.root.state('zoomed')
        except tk.TclError:
            self.root.attributes('-zoomed', True)
        
        self.bg_color = "#ffffff"
        self.dark_cyan = "#0a2129"
        self.accent_color = "#062340" 
        self.root.configure(bg=self.bg_color)
        
        self.drives = {}
        self.queue = []
        self.photo_references = [] 
        self.is_processing = False
        
        # Setup Animation Engine for Banner Gradient & Pulse Bar
        self.canvas_images = {}
        self.gradient_offset = 0
        self.pulse_phase = 0.0
        self.generate_master_gradient()

        # --- HEADER ROW ---
        header_container = tk.Frame(root, bg=self.bg_color)
        header_container.pack(fill="x", padx=20, pady=10)

        # Right Panel
        right_panel = tk.Frame(header_container, bg=self.bg_color)
        right_panel.pack(side="right", fill="y", anchor="e")

        # Padded Hamburger Menu 
        self.hamburger_canvas = tk.Canvas(right_panel, bg=self.bg_color, highlightthickness=0, width=42, height=38)
        self.hamburger_canvas.pack(side="top", anchor="e", pady=(0, 5), padx=5)
        self.hamburger_canvas.bind("<Configure>", lambda e: self.draw_rounded(self.hamburger_canvas, e.width, e.height, 10, "#ffffff", "☰", text_color="black", font=("Arial", 16), pad=4))
        self.hamburger_canvas.bind("<Button-1>", lambda e: self.show_about())

        controls_row = tk.Frame(right_panel, bg=self.bg_color)
        controls_row.pack(side="top", anchor="e")

        self.combo_bg = tk.Canvas(controls_row, bg=self.bg_color, highlightthickness=0, width=230, height=35)
        self.combo_bg.pack(side="left")
        self.combo_bg.bind("<Configure>", lambda e: self.draw_rounded(self.combo_bg, e.width, e.height, 6, "#ffffff", border_color="#cccccc"))
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("White.TCombobox", fieldbackground="#ffffff", background="#ffffff", foreground="black", borderwidth=0, arrowcolor="black")
        
        self.drive_combo = ttk.Combobox(self.combo_bg, state="readonly", style="White.TCombobox")
        self.drive_combo.place(relx=0.5, rely=0.5, relwidth=0.92, anchor="center")

        self.refresh_canvas = tk.Canvas(controls_row, bg=self.bg_color, highlightthickness=0, width=130, height=35)
        self.refresh_canvas.pack(side="left", padx=(10, 0))
        self.refresh_canvas.bind("<Configure>", lambda e: self.draw_rounded(self.refresh_canvas, e.width, e.height, 6, "#ffffff", "🔄 REFRESH", text_color="black", font=("Arial", 9, "bold"), border_color="#cccccc"))
        self.refresh_canvas.bind("<Button-1>", lambda e: self.scan_usb())

        # Left Panel (Banner)
        self.banner_canvas = tk.Canvas(header_container, bg=self.bg_color, highlightthickness=0, height=90)
        self.banner_canvas.pack(side="left", fill="both", expand=True, padx=(0, 20))

        # --- MAIN UI (2 Columns) ---
        main_content = tk.Frame(root, bg=self.bg_color)
        main_content.pack(fill="both", expand=True, padx=20, pady=(10, 0))

        # LEFT COLUMN: Tabs & Search
        left_col = tk.Frame(main_content, bg=self.bg_color)
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))

        tab_bar = tk.Frame(left_col, bg=self.bg_color)
        tab_bar.pack(fill="x", pady=(0, 10))
        
        self.active_tab = "audio"
        
        # Left Aligned Fixed-Width Tabs (ADDED <Configure> BINDINGS FIX)
        self.music_tab_btn = tk.Canvas(tab_bar, bg=self.bg_color, highlightthickness=0, width=190, height=45)
        self.music_tab_btn.pack(side="left", padx=(0, 5))
        self.music_tab_btn.bind("<Configure>", lambda e: self.draw_tab(self.music_tab_btn, e.width, e.height, "audio", "🎵 MUSIC"))
        self.music_tab_btn.bind("<Button-1>", lambda e: self.switch_tab("audio"))
        
        self.video_tab_btn = tk.Canvas(tab_bar, bg=self.bg_color, highlightthickness=0, width=190, height=45)
        self.video_tab_btn.pack(side="left", padx=(5, 0))
        self.video_tab_btn.bind("<Configure>", lambda e: self.draw_tab(self.video_tab_btn, e.width, e.height, "video", "🎬 VIDEO"))
        self.video_tab_btn.bind("<Button-1>", lambda e: self.switch_tab("video"))

        self.playlist_tab_btn = tk.Canvas(tab_bar, bg=self.bg_color, highlightthickness=0, width=190, height=45)
        self.playlist_tab_btn.pack(side="left", padx=(5, 0))
        self.playlist_tab_btn.bind("<Configure>", lambda e: self.draw_tab(self.playlist_tab_btn, e.width, e.height, "playlist", "🎶 PLAYLIST"))
        self.playlist_tab_btn.bind("<Button-1>", lambda e: self.switch_tab("playlist"))

        self.tab_container = tk.Frame(left_col, bg=self.bg_color)
        self.tab_container.pack(fill="both", expand=True)

        self.tab_music = tk.Frame(self.tab_container, bg=self.bg_color)
        self.tab_video = tk.Frame(self.tab_container, bg=self.bg_color)
        self.tab_playlist = tk.Frame(self.tab_container, bg=self.bg_color)

        self.setup_tab(self.tab_music, "audio")
        self.setup_tab(self.tab_video, "video")
        self.setup_tab(self.tab_playlist, "playlist")

        # RIGHT COLUMN: Queue & Logs
        right_col = tk.Frame(main_content, bg=self.bg_color)
        right_col.pack(side="right", fill="both", expand=True, padx=(10, 0))

        # Queue Header with Clear All Button
        q_header = tk.Frame(right_col, bg=self.bg_color)
        q_header.pack(fill="x", pady=(0, 5))
        tk.Label(q_header, text="Transfer Queue", bg=self.bg_color, fg=self.accent_color, font=("MS Sans Serif", 10, "bold")).pack(side="left")
        
        self.clear_q_btn = tk.Canvas(q_header, bg=self.bg_color, highlightthickness=0, width=70, height=25)
        self.clear_q_btn.pack(side="right")
        self.clear_q_btn.bind("<Configure>", lambda e: self.draw_rounded(self.clear_q_btn, e.width, e.height, 10, "#e0e0e0", "Clear All", text_color="black", font=("Arial", 8, "bold")))
        self.clear_q_btn.bind("<Button-1>", lambda e: self.clear_queue())

        queue_border = tk.Frame(right_col, bg="#cccccc", padx=1, pady=1)
        queue_border.pack(fill="both", expand=True, pady=(0, 10))

        self.queue_canvas = tk.Canvas(queue_border, bg="#f0f0f0", highlightthickness=0)
        queue_scroll = tk.Scrollbar(queue_border, orient="vertical", command=self.queue_canvas.yview)
        self.queue_frame = tk.Frame(self.queue_canvas, bg="#f0f0f0")
        
        self.queue_window = self.queue_canvas.create_window((0,0), window=self.queue_frame, anchor="nw")
        self.queue_canvas.bind("<Configure>", lambda e: self.queue_canvas.itemconfig(self.queue_window, width=e.width))
        
        self.queue_canvas.configure(yscrollcommand=queue_scroll.set)
        self.queue_canvas.pack(side="left", fill="both", expand=True)
        queue_scroll.pack(side="right", fill="y")

        log_frame = tk.LabelFrame(right_col, text="More info", bg=self.bg_color, fg=self.accent_color, font=("MS Sans Serif", 9), height=150)
        log_frame.pack(fill="x")
        log_frame.pack_propagate(False)
        
        self.log_text = tk.Text(log_frame, bg="#f8f8f8", fg="black", font=("Consolas", 8), state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

        # --- FOOTER ---
        self.current_progress = 0
        self.progress_canvas = tk.Canvas(root, bg=self.bg_color, highlightthickness=0, height=14)
        self.progress_canvas.pack(fill="x", padx=20, pady=5)
        self.progress_canvas.bind("<Configure>", lambda e: self.update_progress())

        self.push_btn_canvas = tk.Canvas(root, bg=self.bg_color, highlightthickness=0, height=50)
        self.push_btn_canvas.pack(fill="x", padx=20, pady=10)
        self.btn_state = "normal"
        self.btn_text = "SEND QUEUE TO PSP"
        self.push_btn_canvas.bind("<Configure>", self.draw_push_btn)
        self.push_btn_canvas.bind("<Button-1>", lambda e: self.process_queue() if self.btn_state == "normal" else None)

        # Start Systems
        self.scan_usb()
        self.switch_tab("audio")
        self.root.update_idletasks() 
        
        # We can leave these here as fallbacks, but the <Configure> bindings above will handle the Windows bug
        m_w, m_h = self.music_tab_btn.winfo_width(), self.music_tab_btn.winfo_height()
        if m_w > 1: self.draw_tab(self.music_tab_btn, m_w, m_h, "audio", "🎵 MUSIC")
        v_w, v_h = self.video_tab_btn.winfo_width(), self.video_tab_btn.winfo_height()
        if v_w > 1: self.draw_tab(self.video_tab_btn, v_w, v_h, "video", "🎬 VIDEO")
        p_w, p_h = self.playlist_tab_btn.winfo_width(), self.playlist_tab_btn.winfo_height()
        if p_w > 1: self.draw_tab(self.playlist_tab_btn, p_w, p_h, "playlist", "🎶 PLAYLIST")
        
        self.root.after(50, self.animate_ui)

    # --- ANIMATION & DRAWING ENGINE ---
    def generate_master_gradient(self):
        size = 3000
        base = Image.new('RGB', (size, 1))
        for x in range(size):
            ratio = (x % 1500) / 1500.0
            ratio = ratio * 2 if ratio < 0.5 else (1 - ratio) * 2
            base.putpixel((x, 0), (int(10 * ratio), int(33 * ratio), int(41 * ratio)))
        base = base.resize((size, size))
        self.master_gradient = base.rotate(45)

    def get_pulsating_color(self):
        t = (1 - math.cos(self.pulse_phase)) / 2
        r = int(0 + (224 - 0) * t)
        g = int(191 + (247 - 191) * t)
        b = int(255 + (250 - 255) * t)
        return f"#{r:02x}{g:02x}{b:02x}"

    def animate_ui(self):
        self.gradient_offset = (self.gradient_offset + 1) % 1500
        self.pulse_phase += 0.1
        if self.pulse_phase > 2 * math.pi:
            self.pulse_phase -= 2 * math.pi
            
        b_w, b_h = self.banner_canvas.winfo_width(), self.banner_canvas.winfo_height()
        if b_w > 10:
            self.draw_gradient(self.banner_canvas, b_w, b_h, 6, "PSP Media Suite", font=("MS Sans Serif", 24, "bold"), anchor="w")
            
        if self.current_progress > 0:
            self.update_progress() 
            
        self.root.after(40, self.animate_ui) 

    def draw_rounded(self, canvas, w, h, rad, color, text="", font=("MS Sans Serif", 10, "bold"), text_color="white", border_color="", pad=1, clear=True):
        if clear:
            canvas.delete("all")
        if w <= 2*pad or h <= 2*pad: return
        
        x0, y0 = pad, pad
        x1, y1 = w - pad - 1, h - pad - 1
        rad = min(rad, (x1-x0)//2, (y1-y0)//2)
        
        def draw_shape(cx0, cy0, cx1, cy1, cr, ccolor):
            canvas.create_arc(cx0, cy0, cx0+cr*2, cy0+cr*2, start=90, extent=90, fill=ccolor, outline="")
            canvas.create_arc(cx1-cr*2, cy0, cx1, cy0+cr*2, start=0, extent=90, fill=ccolor, outline="")
            canvas.create_arc(0, cy1-cr*2, cx0+cr*2, cy1, start=180, extent=90, fill=ccolor, outline="")
            canvas.create_arc(cx1-cr*2, cy1-cr*2, cx1, cy1, start=270, extent=90, fill=ccolor, outline="")
            canvas.create_rectangle(cx0+cr, cy0, cx1-cr, cy1, fill=ccolor, outline="")
            canvas.create_rectangle(cx0, cy0+cr, cx1, cy1-cr, fill=ccolor, outline="")

        if border_color:
            draw_shape(x0, y0, x1, y1, rad, border_color)
            draw_shape(x0+1, y0+1, x1-1, y1-1, max(1, rad-1), color)
        else:
            draw_shape(x0, y0, x1, y1, rad, color)
            
        if text:
            txt_id = canvas.create_text(w/2, h/2, text=text, font=font, fill=text_color)
            canvas.tag_bind(txt_id, "<Button-1>", lambda e: canvas.event_generate("<Button-1>"))

    def draw_gradient(self, canvas, w, h, rad, text="", font=("MS Sans Serif", 10, "bold"), text_color="white", anchor="center"):
        canvas.delete("all")
        if w <= 2 or h <= 2: return
        x0, y0 = 1, 1
        x1, y1 = w - 2, h - 2
        rad = min(rad, (x1-x0)//2, (y1-y0)//2)
        
        box = (self.gradient_offset, self.gradient_offset, self.gradient_offset + (x1-x0), self.gradient_offset + (y1-y0))
        img = self.master_gradient.crop(box)
        mask = Image.new('L', ((x1-x0), (y1-y0)), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, (x1-x0)-1, (y1-y0)-1), rad, fill=255)
        img.putalpha(mask)
        
        photo = ImageTk.PhotoImage(img)
        self.canvas_images[canvas] = photo
        
        canvas.create_image(x0, y0, anchor="nw", image=photo)
        if text:
            txt_x = w/2 if anchor == "center" else 30
            txt_id = canvas.create_text(txt_x, h/2, text=text, font=font, fill=text_color, anchor=anchor)
            canvas.tag_bind(txt_id, "<Button-1>", lambda e: canvas.event_generate("<Button-1>"))

    def draw_tab(self, canvas, w, h, tab_name, text):
        if w <= 4 or h <= 4: return
        if self.active_tab == tab_name:
            self.draw_rounded(canvas, w, h, 6, self.accent_color, text, text_color="white")
        else:
            self.draw_rounded(canvas, w, h, 6, "#e0e0e0", text, text_color="black")

    def switch_tab(self, tab_name):
        self.active_tab = tab_name
        self.tab_video.pack_forget()
        self.tab_music.pack_forget()
        self.tab_playlist.pack_forget()

        if tab_name == "audio":
            self.tab_music.pack(fill="both", expand=True)
        elif tab_name == "video":
            self.tab_video.pack(fill="both", expand=True)
        elif tab_name == "playlist":
            self.tab_playlist.pack(fill="both", expand=True)
            
        self.root.update_idletasks() 
        
        m_w, m_h = self.music_tab_btn.winfo_width(), self.music_tab_btn.winfo_height()
        if m_w > 1: self.draw_tab(self.music_tab_btn, m_w, m_h, "audio", "🎵 MUSIC")
        
        v_w, v_h = self.video_tab_btn.winfo_width(), self.video_tab_btn.winfo_height()
        if v_w > 1: self.draw_tab(self.video_tab_btn, v_w, v_h, "video", "🎬 VIDEO")
        
        p_w, p_h = self.playlist_tab_btn.winfo_width(), self.playlist_tab_btn.winfo_height()
        if p_w > 1: self.draw_tab(self.playlist_tab_btn, p_w, p_h, "playlist", "🎶 PLAYLIST")

    def update_progress(self, val=None):
        if val is not None:
            self.current_progress = val
            if val >= 100:
                self.root.after(1500, lambda: self.update_progress(0))

        w = self.progress_canvas.winfo_width()
        h = self.progress_canvas.winfo_height()
        self.progress_canvas.delete("all")
        
        if w > 10 and self.current_progress > 0:
            rad = h // 2
            self.draw_rounded(self.progress_canvas, w, h, rad, "#e0e0e0", clear=False)
            
            fill_w = max(rad*2, (w * self.current_progress) / 100.0)
            bar_color = self.get_pulsating_color()
            self.draw_rounded(self.progress_canvas, int(fill_w), h, rad, bar_color, clear=False)
            
        self.root.update_idletasks()

    def draw_push_btn(self, event=None):
        w = self.push_btn_canvas.winfo_width()
        h = self.push_btn_canvas.winfo_height()
        if w <= 1 or h <= 1: return
        
        if self.is_processing:
            self.draw_rounded(self.push_btn_canvas, w, h, 6, "#ffff00", self.btn_text, text_color="black", font=("MS Sans Serif", 14, "bold"))
        elif self.btn_state == "normal":
            self.draw_rounded(self.push_btn_canvas, w, h, 6, self.accent_color, self.btn_text, text_color="white", font=("MS Sans Serif", 14, "bold"))
        else:
            self.draw_rounded(self.push_btn_canvas, w, h, 6, "#a0a0a0", self.btn_text, text_color="black", font=("MS Sans Serif", 14, "bold"))

    def update_push_btn(self, text, state):
        self.btn_text = text
        self.btn_state = state
        self.push_btn_canvas.event_generate("<Configure>")

    # --- UI COMPONENTS ---
    def show_about(self):
        about = tk.Toplevel(self.root)
        about.title("About")
        about.geometry("250x340")
        about.configure(bg=self.bg_color)
        about.resizable(False, False)
        
        icon_path = get_resource_path("Icon.png")
        if os.path.exists(icon_path):
            try:
                img = Image.open(icon_path)
                try: resample_filter = Image.Resampling.LANCZOS
                except AttributeError: resample_filter = Image.LANCZOS
                img = img.resize((64, 64), resample_filter)
                photo = ImageTk.PhotoImage(img)
                lbl = tk.Label(about, image=photo, bg=self.bg_color)
                lbl.image = photo
                lbl.pack(pady=10)
            except: pass
                
        tk.Label(about, text="PSP Media Suite", font=("Arial", 12, "bold"), bg=self.bg_color).pack()
        tk.Label(about, text="by vmg265", font=("Arial", 10), bg=self.bg_color).pack()
        tk.Label(about, text="v1.5", font=("Arial", 9), bg=self.bg_color).pack(pady=5)
        
        tk.Button(about, text="GitHub", command=lambda: webbrowser.open("https://github.com/vmg265/PSP-Media-Suite"), width=15).pack(pady=5)
        tk.Button(about, text="Buy me a tea?", command=lambda: webbrowser.open("https://rzp.io/rzp/pFrhgY8"), width=15).pack(pady=5)
        tk.Button(about, text="Having issues?", command=self.show_troubleshooter, width=15).pack(pady=5)

    def show_troubleshooter(self):
        trouble_win = tk.Toplevel(self.root)
        trouble_win.title("Troubleshooter")
        trouble_win.geometry("550x400")
        trouble_win.configure(bg=self.bg_color)
        
        txt = tk.Text(trouble_win, wrap="word", bg="#f8f8f8", fg="black", font=("Arial", 10))
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        
        ts_path = get_resource_path("troubleshooter_box.txt")
        if os.path.exists(ts_path):
            try:
                with open(ts_path, "r", encoding="utf-8") as f:
                    txt.insert(tk.END, f.read())
            except Exception as e:
                txt.insert(tk.END, f"Error reading file: {e}")
        else:
            txt.insert(tk.END, "troubleshooter_box.txt not found. Please ensure it is in the same directory as the executable.")
            
        txt.config(state="disabled")

    def write_log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"> {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

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

        self.drive_combo['values'] = list(set(found))
        if found: self.drive_combo.current(0)
        else: self.drive_combo.set("No Drive Found")

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
        search_bg = tk.Canvas(parent, bg=self.bg_color, highlightthickness=0, height=35)
        search_bg.pack(fill="x", padx=10, pady=10)
        search_bg.bind("<Configure>", lambda e: self.draw_rounded(e.widget, e.width, e.height, 6, "#ffffff", border_color="#cccccc"))

        search_var = tk.StringVar()
        entry = tk.Entry(search_bg, textvariable=search_var, fg="black", font=("MS Sans Serif", 12), borderwidth=0, relief="flat", bg="#ffffff", insertbackground="black")
        entry.place(relx=0.03, rely=0.5, relwidth=0.94, anchor="w")
        
        entry.insert(0, "Search YouTube...")
        entry.bind("<FocusIn>", lambda e: self.clear_ph(entry))
        entry.bind("<FocusOut>", lambda e: self.add_ph(entry))
        entry.bind('<Return>', lambda e: self.search(search_var.get(), parent, media_type))

        if media_type != "playlist":
            btn_text = "📁 Add local Music" if media_type == "audio" else "📁 Add local Video"
            local_btn = tk.Canvas(parent, bg=self.bg_color, highlightthickness=0, height=35)
            local_btn.pack(fill="x", padx=10, pady=(0, 10))
            local_btn.bind("<Configure>", lambda e, c=local_btn, t=btn_text: self.draw_rounded(c, e.width, e.height, 6, "#ffffff", t, text_color="black", font=("Arial", 10, "bold"), border_color="#cccccc"))
            local_btn.bind("<Button-1>", lambda e: self.add_local_file(media_type))

        results_canvas = tk.Canvas(parent, bg="#fff", highlightthickness=1)
        scroll = tk.Scrollbar(parent, orient="vertical", command=results_canvas.yview)
        results_frame = tk.Frame(results_canvas, bg="#fff")
        
        parent.res_window = results_canvas.create_window((0,0), window=results_frame, anchor="nw")
        results_canvas.bind("<Configure>", lambda e, cvs=results_canvas, wid=parent.res_window: cvs.itemconfig(wid, width=e.width))
        
        parent.results_canvas = results_canvas
        parent.results_frame = results_frame
        parent.cached_results = []
        parent.render_index = 0
        parent.load_more_btn = None
        
        results_canvas.configure(yscrollcommand=scroll.set)
        results_canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        scroll.pack(side="right", fill="y", pady=5)
        self.bind_mousewheel(results_canvas, results_frame)

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

    def add_ph(self, entry):
        if not entry.get():
            entry.insert(0, "Search YouTube...")

    def add_local_file(self, media_type):
        filetypes = [("Audio Files", "*.mp3 *.ogg *.opus *.m4a *.wav")] if media_type == "audio" else [("Video Files", "*.mp4 *.mkv *.avi *.mov *.webm")]
        filepaths = filedialog.askopenfilenames(title=f"Select Local {media_type.capitalize()}", filetypes=filetypes)
        for path in filepaths:
            filename = os.path.basename(path)
            name_no_ext, _ = os.path.splitext(filename)
            item = {
                'title': f"(Local) {name_no_ext}",
                'url': path,
                'is_local': True,
                'pil_image': None,
                'formatted_time': 'Local',
                'raw_thumb_url': None
            }
            self.add_to_queue(item, media_type)

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
        self.update_progress(20)
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
                    if info.get('entries'):
                        parent.cached_results = list(info['entries'])
                    else:
                        parent.cached_results = [info]
                        
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
        end = start + 8
        chunk = parent.cached_results[start:end]
        
        for r in chunk:
            url = r.get('url') or r.get('webpage_url') or r.get('original_url')
            if not url:
                vid_id = str(r.get('id', ''))
                if r.get('_type') == 'playlist' or vid_id.startswith('PL') or vid_id.startswith('OL') or vid_id.startswith('RD'):
                    url = f"https://www.youtube.com/playlist?list={vid_id}"
                else:
                    url = f"https://www.youtube.com/watch?v={vid_id}"
                    
            if "watch?v=PL" in url or "watch?v=OL" in url:
                url = url.replace("watch?v=", "playlist?list=")
                
            r['url'] = url
            
            thumb_url = r.get('thumbnail')
            if not thumb_url and r.get('thumbnails'): thumb_url = r['thumbnails'][-1].get('url')
            
            r['raw_thumb_url'] = thumb_url 
            r['pil_image'] = self.fetch_image_bytes(thumb_url) if thumb_url else None
            r['formatted_time'] = self.format_time(r.get('duration', 0))
            
        self.root.after(0, self.render_chunk, chunk, parent, media_type)

    def render_chunk(self, chunk, parent, media_type):
        for item in chunk:
            if not item.get('url'): continue
            
            row = tk.Frame(parent.results_frame, bg="white", height=55)
            row.pack(fill="x", anchor="w", pady=2)
            row.pack_propagate(False) 
            
            if media_type == "audio":
                btn_text = "➕ Add Music"
                btn_color = "#ffffcc"
            elif media_type == "video":
                btn_text = "➕ Add Video"
                btn_color = "#ffcccc"
            else:
                btn_text = "➕ Add Playlist"
                btn_color = "#e6ccff" 
            
            add_cvs = tk.Canvas(row, bg="white", highlightthickness=0, width=120, height=35)
            add_cvs.pack(side="right", padx=10)
            self.draw_rounded(add_cvs, 120, 35, 6, btn_color, btn_text, text_color="black", font=("Arial", 10, "bold"))
            add_cvs.bind("<Button-1>", lambda e, i=item, mt=media_type: self.add_to_queue(i, mt))

            if item.get('pil_image'):
                photo = ImageTk.PhotoImage(item['pil_image'])
                self.photo_references.append(photo)
                tk.Label(row, image=photo, bg="white").pack(side="left", padx=10)
            else:
                tk.Frame(row, bg="white", width=80, height=45).pack(side="left", padx=10)
            
            display_text = f"{item['title'][:55]}  [{item['formatted_time']}]"
            tk.Label(row, text=display_text, bg="white", font=("Arial", 10), anchor="w", justify="left").pack(side="left", fill="both", expand=True, padx=5)
            
        parent.render_index += 8
        
        if parent.render_index < len(parent.cached_results):
            parent.load_more_btn = tk.Canvas(parent.results_frame, bg="white", highlightthickness=0, width=250, height=35)
            parent.load_more_btn.pack(pady=10)
            self.draw_rounded(parent.load_more_btn, 250, 35, 6, "#e0e0e0", "🔽 LOAD MORE", font=("Arial", 10, "bold"), text_color="black")
            parent.load_more_btn.bind("<Button-1>", lambda e: self.trigger_load_chunk(parent, media_type))
            
        self.root.update_idletasks()
        parent.results_canvas.configure(scrollregion=parent.results_canvas.bbox("all"))
        self.update_progress(100)

    def add_to_queue(self, item, media_type):
        current_time = time.time()
        if hasattr(self, 'last_added_time') and hasattr(self, 'last_added_url'):
            if self.last_added_url == item['url'] and (current_time - self.last_added_time < 0.6):
                return
        self.last_added_url = item['url']
        self.last_added_time = current_time

        q_row = tk.Frame(self.queue_frame, bg="#f0f0f0", height=55)
        q_row.pack(fill="x", anchor="w", pady=2)
        q_row.pack_propagate(False)
        
        if media_type == "audio": icon = "🎵 "
        elif media_type == "video": icon = "🎬 "
        else: icon = "🎶 "
        
        status_cvs = tk.Canvas(q_row, bg="#f0f0f0", highlightthickness=0, width=36, height=36)
        status_cvs.pack(side="right", padx=15)
        self.draw_rounded(status_cvs, 36, 36, 6, "#e0e0e0", pad=4)

        thumb_container = tk.Frame(q_row, bg="#f0f0f0", width=60, height=55)
        thumb_container.pack(side="left", padx=(5, 10))
        thumb_container.pack_propagate(False)

        thumb_cvs = tk.Canvas(thumb_container, bg="#f0f0f0", highlightthickness=0, width=60, height=45)
        thumb_cvs.place(relx=0.5, rely=0.5, anchor="center")

        if item.get('pil_image'):
            photo = ImageTk.PhotoImage(item['pil_image'].resize((60, 34)))
            self.photo_references.append(photo)
            thumb_cvs.create_image(0, 5, anchor="nw", image=photo)
        else:
            thumb_cvs.create_rectangle(0, 5, 60, 39, fill="#cccccc", outline="")

        x_btn = tk.Canvas(thumb_container, bg="#f0f0f0", highlightthickness=0, width=24, height=24)
        x_btn.place(x=0, y=0)
        self.draw_rounded(x_btn, 24, 24, 10, "#ff4444", "X", font=("Arial", 10, "bold"))

        q_text = f"{icon} [{item['formatted_time']}] {item['title'][:50]}"
        lbl = tk.Label(q_row, text=q_text, bg="#f0f0f0", font=("Arial", 9), anchor="w", justify="left")
        lbl.pack(side="left", fill="both", expand=True)

        q_data = {
            'status': 'pending',
            'type': media_type, 
            'url': item['url'], 
            'title': item['title'], 
            'thumb': item.get('raw_thumb_url'),
            'is_local': item.get('is_local', False),
            'lbl': lbl,
            'status_cvs': status_cvs,
            'q_row': q_row
        }
        
        def remove_item(e):
            if not self.is_processing: self.remove_from_queue(q_row, q_data)
            
        x_btn.bind("<Button-1>", remove_item)

        self.queue.append(q_data)
        self.root.update_idletasks()
        self.queue_canvas.configure(scrollregion=self.queue_canvas.bbox("all"))

    def remove_from_queue(self, row_widget, q_data):
        row_widget.destroy()
        if q_data in self.queue: self.queue.remove(q_data)
        self.root.update_idletasks()
        self.queue_canvas.configure(scrollregion=self.queue_canvas.bbox("all"))

    def clear_queue(self):
        if self.is_processing: return
        for item in self.queue:
            item['q_row'].destroy()
        self.queue.clear()
        self.root.update_idletasks()
        self.queue_canvas.configure(scrollregion=self.queue_canvas.bbox("all"))

    def pulse_item(self, item, toggle=False):
        if item.get('status') != 'processing': return
        color = "#d9f2f2" if toggle else "#f0f0f0" 
        self.draw_rounded(item['status_cvs'], 36, 36, 6, color, "⏳", text_color="black", font=("Arial", 14), pad=4)
        self.root.after(600, self.pulse_item, item, not toggle)

    def process_queue(self):
        drive_name = self.drive_combo.get()
        if drive_name not in self.drives or not self.queue: return
        
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
            if item['status'] == 'success': continue
            
            self.root.after(0, lambda v=(i/total)*100: self.update_progress(v))
            self.root.after(0, lambda msg=f"Processing: {item['title'][:40]}": self.write_log(msg))
            
            clean_title = os.path.splitext(item['title'])[0] if item.get('is_local') else item['title']
            clean_name = "".join(x for x in clean_title if x.isalnum() or x in " .-_")[:100]
            item['status'] = 'processing'
            self.root.after(0, self.pulse_item, item)
            
            for f in os.listdir("."):
                if f.startswith("temp.") or f.startswith("temp_raw.") or f == "temp_thumb.jpg" or f == "cover.jpg":
                    try: os.remove(f)
                    except: pass
            
            try:
                if item['type'] == 'playlist':
                    target_dir = os.path.join(drive_path, "MUSIC")
                    if not os.path.exists(target_dir): os.makedirs(target_dir)
                    playlist_dir = os.path.join(drive_path, "PSP", "PLAYLIST", "MUSIC")
                    if not os.path.exists(playlist_dir): os.makedirs(playlist_dir)
                    
                    clean_pl_title = "".join(x for x in item['title'] if x.isalnum() or x in " .-_")[:100]
                    m3u8_lines = []
                    
                    opts = {'quiet': True, 'extract_flat': True}
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info_dict = ydl.extract_info(item['url'], download=False)
                    
                    entries = info_dict.get('entries', [info_dict])
                    
                    for entry_idx, entry in enumerate(entries):
                        if not entry: continue
                        entry_url = entry.get('url')
                        if not entry_url: entry_url = f"https://www.youtube.com/watch?v={entry.get('id')}"
                        
                        entry_title = entry.get('title', f"Track {entry_idx+1}")
                        clean_name = "".join(x for x in entry_title if x.isalnum() or x in " .-_")[:100]
                        
                        self.root.after(0, lambda msg=f"Downloading: {entry_title[:30]}": self.write_log(msg))
                        
                        dl_opts = {
                            'format': 'bestaudio/best', 'ffmpeg_location': ff_path, 'outtmpl': 'temp_raw.%(ext)s', 'nopart': True,
                            'continuedl': False, 'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
                            'postprocessor_args': ['-map_metadata', '-1'] 
                        }
                        
                        try:
                            with yt_dlp.YoutubeDL(dl_opts) as ydl2:
                                entry_info = ydl2.extract_info(entry_url, download=True)
                                img = self._get_best_thumbnail(entry_info, entry.get('thumbnail') or entry.get('thumbnails', [{}])[-1].get('url'))
                                has_cover = False
                                if img:
                                    try:
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
                                    except Exception as e: self.write_log(f"Cover Error: {e}")
                            
                            audio = MP3("temp_raw.mp3", ID3=ID3)
                            if audio.tags is None: audio.add_tags()
                            else: audio.tags.clear()
                            audio.tags.add(TIT2(encoding=3, text=entry_title))
                            audio.tags.add(TPE1(encoding=3, text="YouTube Audio"))
                            audio.tags.add(TALB(encoding=3, text=item['title'])) 
                            if has_cover and os.path.exists("cover.jpg"):
                                with open("cover.jpg", "rb") as albumart:
                                    audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=albumart.read()))
                            audio.save(v2_version=3, v1=2) 
                            shutil.move("temp_raw.mp3", os.path.join(target_dir, clean_name + ".mp3"))
                            
                            m3u8_lines.append(f"\\MUSIC\\{clean_name}.mp3")
                        except Exception as e:
                            self.write_log(f"Failed entry {entry_title}: {e}")
                        
                        for f in os.listdir("."):
                            if f.startswith("temp.") or f.startswith("temp_raw.") or f == "temp_thumb.jpg" or f == "cover.jpg":
                                try: os.remove(f)
                                except: pass
                    
                    if m3u8_lines:
                        m3u8_path = os.path.join(playlist_dir, clean_pl_title + ".m3u8")
                        with open(m3u8_path, "w", encoding="utf-8") as f:
                            f.write("\n".join(m3u8_lines))
                            
                    item['status'] = 'success'
                    self.root.after(0, lambda i=item: self.draw_rounded(i['status_cvs'], 36, 36, 6, "#d4f0d4", "✓", text_color="black", font=("Arial", 14, "bold"), pad=4))

                elif item['type'] == 'audio':
                    clean_title = os.path.splitext(item['title'])[0] if item.get('is_local') else item['title']
                    clean_name = "".join(x for x in clean_title if x.isalnum() or x in " .-_")[:100]
                    target_dir = os.path.join(drive_path, "MUSIC")
                    if not os.path.exists(target_dir): os.makedirs(target_dir)
                    
                    if item.get('is_local'):
                        subprocess.run([ff_path, "-y", "-i", item['url'], "-vn", "-ar", "44100", "-ac", "2", "-b:a", "192k", "temp_raw.mp3"], startupinfo=startupinfo)
                    else:
                        opts = {
                            'format': 'bestaudio/best', 'ffmpeg_location': ff_path, 'outtmpl': 'temp_raw.%(ext)s', 'nopart': True,
                            'continuedl': False, 'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
                            'postprocessor_args': ['-map_metadata', '-1'] 
                        }
                        with yt_dlp.YoutubeDL(opts) as ydl: 
                            info_dict = ydl.extract_info(item['url'], download=True)
                            
                            img = self._get_best_thumbnail(info_dict, item.get('thumb'))
                            if img:
                                try:
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
                                except Exception as e: self.write_log(f"Cover Error: {e}")
                    
                    audio = MP3("temp_raw.mp3", ID3=ID3)
                    if audio.tags is None: audio.add_tags()
                    else: audio.tags.clear()
                    
                    audio.tags.add(TIT2(encoding=3, text=item["title"]))
                    audio.tags.add(TPE1(encoding=3, text="YouTube Audio" if not item.get('is_local') else "Local Audio"))
                    audio.tags.add(TALB(encoding=3, text="PSP Media Suite"))
                    
                    if 'has_cover' in locals() and has_cover and os.path.exists("cover.jpg"):
                        with open("cover.jpg", "rb") as albumart:
                            audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=albumart.read()))
                    
                    audio.save(v2_version=3, v1=2) 
                    shutil.move("temp_raw.mp3", os.path.join(target_dir, clean_name + ".mp3"))
                    
                    item['status'] = 'success'
                    self.root.after(0, lambda i=item: self.draw_rounded(i['status_cvs'], 36, 36, 6, "#d4f0d4", "✓", text_color="black", font=("Arial", 14, "bold"), pad=4))

                else:
                    clean_title = os.path.splitext(item['title'])[0] if item.get('is_local') else item['title']
                    clean_name = "".join(x for x in clean_title if x.isalnum() or x in " .-_")[:100]
                    target_dir = os.path.join(drive_path, "VIDEO")
                    if not os.path.exists(target_dir): os.makedirs(target_dir)
                    
                    if item.get('is_local'):
                        subprocess.run([ff_path, "-y", "-i", item['url'], "-c:v", "libx264", "-profile:v", "baseline", "-level", "3.0", 
                                        "-pix_fmt", "yuv420p", "-vf", "scale=480:272", "-b:v", "768k", "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "temp.mp4"], startupinfo=startupinfo)
                        try:
                            subprocess.run([ff_path, "-y", "-i", item['url'], "-ss", "00:00:01", "-vframes", "1", "temp_thumb.jpg"], startupinfo=startupinfo)
                            if os.path.exists("temp_thumb.jpg"): 
                                img = Image.open("temp_thumb.jpg")
                        except: pass
                    else:
                        opts = {
                            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', 'ffmpeg_location': ff_path, 'outtmpl': 'temp.%(ext)s', 'nopart': True,
                            'continuedl': False, 'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}],
                            'postprocessor_args': ['-c:v', 'libx264', '-profile:v', 'baseline', '-level', '3.0', '-pix_fmt', 'yuv420p', '-vf', 'scale=480:272', '-b:v', '768k', '-c:a', 'aac', '-b:a', '128k', '-ar', '48000']
                        }
                        with yt_dlp.YoutubeDL(opts) as ydl:
                            info_dict = ydl.extract_info(item['url'], download=True)
                            img = self._get_best_thumbnail(info_dict, item.get('thumb'))
                                
                    if 'img' in locals() and img:
                        try:
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
                        except Exception as e: self.write_log(f".THM Error: {e}")

                    shutil.move("temp.mp4", os.path.join(target_dir, clean_name + ".mp4"))

                    item['status'] = 'success'
                    self.root.after(0, lambda i=item: self.draw_rounded(i['status_cvs'], 36, 36, 6, "#d4f0d4", "✓", text_color="black", font=("Arial", 14, "bold"), pad=4))

            except Exception as e:
                self.write_log(f"Transfer Error: {e}")
                item['status'] = 'error'
                self.root.after(0, lambda i=item: self.draw_rounded(i['status_cvs'], 36, 36, 6, "#ffd9d9", "X", text_color="black", font=("Arial", 14, "bold"), pad=4))
            
            for f in os.listdir("."):
                if f.startswith("temp.") or f.startswith("temp_raw.") or f == "temp_thumb.jpg" or f == "cover.jpg":
                    try: os.remove(f)
                    except: pass
            if 'img' in locals(): del img 

        self.is_processing = False 
        self.root.after(0, lambda: self.update_progress(100))
        self.root.after(0, lambda: self.update_push_btn("SEND QUEUE TO PSP", "normal"))
        self.root.after(0, lambda: self.write_log("All items uploaded successfully to PSP!"))
        self.root.after(0, lambda: messagebox.showinfo("Queue Complete", "Processing finished! Check queue for statuses."))

if __name__ == "__main__":
    root = tk.Tk()
    app = PSPMediaSuite(root)
    root.mainloop()
