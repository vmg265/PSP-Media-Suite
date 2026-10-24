import os
import sys
import shutil
import threading
import subprocess
import time
import datetime
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from PIL import Image, ImageTk

from ui.theme import Theme, FONT_BODY, FONT_SMALL, FONT_MONO
from ui.icons import get_icon_photo
from ui.components import (
    create_flat_btn,
    create_tab_btn,
    draw_status_indicator,
    draw_rounded_rect,
    AccentButton,
    AnimatedBanner,
    ProgressBar,
    MiniProgressBar,
    MarqueeLabel
)
from ui.dialogs import (
    show_about_dialog,
    show_troubleshooter_dialog,
    show_web_server_info_dialog,
    show_server_started_dialog
)
from ui.local_manager import LocalMediaManagerPanel
from core.config import (
    load_preferences,
    save_preferences,
    clean_filename,
    format_time,
    get_local_ip
)
from core.device import scan_psp_drives
from core.downloader import (
    search_youtube,
    get_best_thumbnail,
    fetch_thumbnail_preview,
    get_ydl_opts
)
from core.transcoder import (
    get_ffmpeg_path,
    crop_and_save_cover,
    crop_and_save_thm,
    apply_mp3_tags,
    transcode_local_audio,
    transcode_video_to_psp,
    extract_video_frame,
    cleanup_temp_files
)
from core.web_server import PSPWebServer
import yt_dlp

class PSPMediaSuite:
    """Main Application Controller and Window."""

    def __init__(self, root):
        self.root = root
        self.root.title("PSP Media Suite v1.7.2")
        self.root.minsize(1040, 680)

        try:
            self.root.state('zoomed')
        except tk.TclError:
            try:
                self.root.attributes('-zoomed', True)
            except Exception:
                self.root.geometry("1280x720")

        self.drives = {}
        self.queue = []
        self.photo_references = []
        self._active_marquees = []
        self.is_processing = False
        self.active_tab = "audio"
        self.current_progress = 0
        self.music_search_mode = "tracks"  # 'tracks' or 'playlists'
        self.video_search_mode = "videos"  # 'videos' or 'playlists'

        # Load Preferences
        prefs = load_preferences()
        self.selected_browser = prefs.get("browser", "None")
        self.is_dark_mode = prefs.get("dark_mode", True)
        Theme.set_theme(self.is_dark_mode)

        # Web Server
        self.web_server = PSPWebServer(
            port=8080,
            log_callback=self.write_log,
            browser_provider=lambda: self.selected_browser
        )

        self._build_ui()
        self.scan_usb()
        self.switch_tab("audio")
        self.root.after(40, self._animate)
        self.root.after(2000, self._poll_drives)

    def _save_prefs(self):
        ok, err = save_preferences(self.selected_browser, self.is_dark_mode)
        if not ok:
            self.write_log(f"Failed to save settings: {err}")

    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass

        style.configure("App.TCombobox", fieldbackground=Theme.SURFACE2, background=Theme.SURFACE2,
                        foreground=Theme.TEXT, selectforeground=Theme.TEXT, selectbackground=Theme.SURFACE2,
                        borderwidth=1, arrowcolor=Theme.ACCENT, insertcolor=Theme.TEXT, relief="flat")
        style.map("App.TCombobox", fieldbackground=[('readonly', Theme.SURFACE2)],
                  background=[('readonly', Theme.SURFACE2)], foreground=[('readonly', Theme.TEXT)])

        self.root.option_add("*TCombobox*Listbox.background", Theme.SURFACE2)
        self.root.option_add("*TCombobox*Listbox.foreground", Theme.TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", Theme.ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.root.option_add("*TCombobox*Listbox.font", FONT_BODY)

        self.root.configure(bg=Theme.BG)

        # ── Animated Header Banner (PS3/PSP XMB fluid wave physics) ──
        self.banner = AnimatedBanner(self.root, height=66)
        self.banner.pack(fill="x")

        right_bar = tk.Frame(self.banner, bg="#081426", highlightbackground="#1e293b", highlightthickness=1)
        right_bar.place(relx=1.0, rely=0.5, anchor="e", x=-16)

        # 1. Hamburger Menu Button (Google Material 'menu' icon)
        self.menu_btn = create_flat_btn(
            right_bar, icon_name="menu", bg="#111c30", fg="#ffffff", hover_bg="#1e293b",
            command=self.show_about, padx=10, pady=6
        )
        self.menu_btn.pack(side="right", padx=(8, 4))

        # 2. Server Button (Google Material 'public' icon)
        self.server_btn = create_flat_btn(
            right_bar, text="Server", icon_name="public", bg="#111c30", fg="#ffffff",
            hover_bg="#1e293b", command=self.toggle_server, padx=10, pady=6
        )
        self.server_btn.pack(side="right", padx=(6, 0))

        # 3. Refresh USB Button (Google Material 'sync' icon)
        refresh_btn = create_flat_btn(
            right_bar, text="Refresh", icon_name="sync", bg="#111c30", fg="#ffffff",
            hover_bg="#1e293b", command=self.scan_usb, padx=10, pady=6
        )
        refresh_btn.pack(side="right", padx=(6, 0))

        # 4. PSP Drive Selector
        self.drive_combo = ttk.Combobox(right_bar, state="readonly", style="App.TCombobox", width=26, font=FONT_BODY)
        self.drive_combo.pack(side="right", padx=(4, 0))
        self.drive_combo.bind("<<ComboboxSelected>>", lambda e: self._on_drive_changed())

        drive_lbl = tk.Label(right_bar, text="Drive:", font=FONT_SMALL, fg="#94a3b8", bg="#081426")
        drive_lbl.pack(side="right", padx=(8, 4))

        self.accent_line = tk.Frame(self.root, bg=Theme.ACCENT, height=2)
        self.accent_line.pack(fill="x")

        # ── Main Tabs Row (Music & Video only - Google Material icons) ──
        tab_row = tk.Frame(self.root, bg=Theme.BG)
        tab_row.pack(fill="x", padx=16, pady=(8, 4))

        self._tab_btns = {}
        for tab_id, label, icon_name in [("audio", "Music", "music_note"), ("video", "Video", "movie")]:
            btn = create_tab_btn(tab_row, label, tab_id, self.switch_tab, icon_name=icon_name)
            btn.pack(side="left", padx=(0, 6))
            self._tab_btns[tab_id] = btn

        # ── Content Panes Container ──
        self.tab_container = tk.Frame(self.root, bg=Theme.BG)
        self.tab_container.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        self.tab_music = tk.Frame(self.tab_container, bg=Theme.BG)
        self.tab_video = tk.Frame(self.tab_container, bg=Theme.BG)

        self._setup_music_tab(self.tab_music)
        self._setup_video_tab(self.tab_video)

        # ── Footer: Improved Status & Dual Progress Bars (No emojis) ──
        footer = tk.Frame(self.root, bg=Theme.SURFACE, height=72)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        border_line = tk.Frame(footer, bg=Theme.BORDER, height=1)
        border_line.pack(fill="x")

        inner_footer = tk.Frame(footer, bg=Theme.SURFACE)
        inner_footer.pack(fill="both", expand=True, padx=16, pady=8)

        # Right: Send Queue Button with Google Material 'upload' icon
        self.send_btn = AccentButton(
            inner_footer,
            "SEND QUEUE VIA USB",
            icon_name="upload",
            width=215,
            height=46,
            command=lambda: self.process_queue() if not self.is_processing else None
        )
        self.send_btn.pack(side="right", padx=(14, 0))

        # Center/Left Area: Responsive Progress & Activity Info
        mid_area = tk.Frame(inner_footer, bg=Theme.SURFACE)
        mid_area.pack(side="left", fill="both", expand=True)

        top_info_row = tk.Frame(mid_area, bg=Theme.SURFACE)
        top_info_row.pack(fill="x", pady=(0, 4))

        # Left: Main Status Label
        self._prog_label = tk.Label(
            top_info_row, text="", font=("Segoe UI", 9, "bold"),
            fg=Theme.TEXT_DIM, bg=Theme.SURFACE, anchor="w"
        )
        self._prog_label.pack(side="left")

        # Right: Queue Multi-Item Progress & Percentage or Ticker
        self._queue_progress_frame = tk.Frame(top_info_row, bg=Theme.SURFACE)
        self._queue_progress_frame.pack(side="right", fill="x", expand=True, padx=(12, 0))

        self.mini_queue_bar = MiniProgressBar(self._queue_progress_frame, width=110, height=8)
        self._queue_prog_lbl = tk.Label(
            self._queue_progress_frame, text="", font=("Segoe UI", 8, "bold"),
            fg="#38bdf8", bg=Theme.SURFACE, anchor="e"
        )

        self.log_ticker_lbl = tk.Label(
            self._queue_progress_frame, text="› Ready", font=FONT_MONO,
            fg=Theme.TEXT_DIM, bg=Theme.SURFACE, anchor="e", cursor="hand2"
        )
        self.log_ticker_lbl.bind("<Button-1>", lambda e: self.show_activity_log_window())
        self.log_ticker_lbl.pack(side="right")

        # Bottom: Pulsating Neon PlayStation Glow Progress Bar
        self.progress_bar = ProgressBar(mid_area, height=11)
        self.progress_bar.pack(fill="x")

        self.log_history = []



    # ── Music Tab Layout ──

    def _setup_music_tab(self, parent):
        panes = tk.Frame(parent, bg=Theme.BG)
        panes.pack(fill="both", expand=True)

        left_side = tk.Frame(panes, bg=Theme.BG)
        left_side.pack(side="left", fill="both", expand=True, padx=(0, 8))

        right_side = tk.Frame(panes, bg=Theme.BG, width=480)
        right_side.pack(side="right", fill="both", padx=(8, 0))
        right_side.pack_propagate(False)

        # Search Bar
        search_row = tk.Frame(left_side, bg=Theme.BG)
        search_row.pack(fill="x", pady=(0, 6))

        search_f = tk.Frame(search_row, bg=Theme.SURFACE2, highlightbackground=Theme.BORDER, highlightthickness=1)
        search_f.pack(side="left", fill="x", expand=True)

        s_icon = get_icon_photo("search", size=15, color=Theme.TEXT_DIM)
        s_lbl = tk.Label(search_f, image=s_icon, bg=Theme.SURFACE2, padx=8)
        s_lbl.image = s_icon
        s_lbl.pack(side="left")

        self.music_search_var = tk.StringVar()
        m_entry = tk.Entry(search_f, textvariable=self.music_search_var, fg=Theme.TEXT_DIM, font=FONT_BODY,
                           borderwidth=0, relief="flat", bg=Theme.SURFACE2, insertbackground=Theme.TEXT)
        m_entry.pack(side="left", fill="both", expand=True, ipady=8)
        m_entry.insert(0, "Search YouTube Music or paste playlist URL…")
        m_entry.bind("<FocusIn>",  lambda e: self.clear_ph(m_entry, "Search YouTube Music"))
        m_entry.bind("<FocusOut>", lambda e: self.add_ph(m_entry, "Search YouTube Music or paste playlist URL…"))
        m_entry.bind("<Return>",   lambda e: self.search(self.music_search_var.get(), parent, "audio"))

        create_flat_btn(search_row, "Search", icon_name="search", bg=Theme.ACCENT, fg="#ffffff", hover_bg=Theme.ACCENT2,
                        command=lambda: self.search(self.music_search_var.get(), parent, "audio"),
                        font=("Segoe UI", 9, "bold")).pack(side="left", padx=(6, 0))

        # Mode and Local Audio Bar
        sub_row = tk.Frame(left_side, bg=Theme.BG)
        sub_row.pack(fill="x", pady=(0, 6))

        self.music_mode_tracks_btn = create_flat_btn(
            sub_row, "Songs", icon_name="music_note", bg=Theme.ACCENT, fg="#ffffff",
            command=lambda: self._set_music_search_mode("tracks"), font=("Segoe UI", 8, "bold")
        )
        self.music_mode_tracks_btn.pack(side="left", padx=(0, 4))

        self.music_mode_pl_btn = create_flat_btn(
            sub_row, "Playlists", icon_name="queue_music", bg=Theme.SURFACE2, fg=Theme.TEXT_DIM,
            command=lambda: self._set_music_search_mode("playlists"), font=("Segoe UI", 8, "bold")
        )
        self.music_mode_pl_btn.pack(side="left", padx=(0, 10))

        create_flat_btn(sub_row, "Add Local Music", icon_name="folder", bg=Theme.SURFACE2, fg=Theme.TEXT, hover_bg=Theme.BORDER,
                        command=lambda: self.add_local_file("audio"), font=("Segoe UI", 8)).pack(side="right")

        # Search Results Canvas
        results_outer = tk.Frame(left_side, bg=Theme.BORDER, padx=1, pady=1)
        results_outer.pack(fill="both", expand=True, pady=(0, 6))

        results_canvas = tk.Canvas(results_outer, bg=Theme.SURFACE, highlightthickness=0)
        scroll = tk.Scrollbar(results_outer, orient="vertical", command=results_canvas.yview)
        results_frame = tk.Frame(results_canvas, bg=Theme.SURFACE)

        parent.res_window = results_canvas.create_window((0, 0), window=results_frame, anchor="nw")
        results_canvas.bind("<Configure>", lambda e, c=results_canvas, w=parent.res_window: c.itemconfig(w, width=e.width))
        results_canvas.configure(yscrollcommand=scroll.set)
        results_canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        parent.results_canvas = results_canvas
        parent.results_frame  = results_frame
        parent.cached_results = []
        parent.render_index   = 0
        parent.load_more_btn  = None
        self._bind_scroll(results_canvas, results_frame)

        # Single-Row Transfer Queue Below Search Results
        self._build_single_row_queue(left_side)

        # Right Side: Embedded Local PSP File & Playlist Management
        self.music_local_panel = LocalMediaManagerPanel(right_side, "audio", self._get_drive_path, self.write_log)
        self.music_local_panel.pack(fill="both", expand=True)

    def _set_music_search_mode(self, mode):
        self.music_search_mode = mode
        if mode == "tracks":
            self.music_mode_tracks_btn.config(bg=Theme.ACCENT, fg="#ffffff")
            self.music_mode_pl_btn.config(bg=Theme.SURFACE2, fg=Theme.TEXT_DIM)
        else:
            self.music_mode_tracks_btn.config(bg=Theme.SURFACE2, fg=Theme.TEXT_DIM)
            self.music_mode_pl_btn.config(bg=Theme.ACCENT, fg="#ffffff")

    # ── Video Tab Layout ──

    def _setup_video_tab(self, parent):
        panes = tk.Frame(parent, bg=Theme.BG)
        panes.pack(fill="both", expand=True)

        left_side = tk.Frame(panes, bg=Theme.BG)
        left_side.pack(side="left", fill="both", expand=True, padx=(0, 8))

        right_side = tk.Frame(panes, bg=Theme.BG, width=480)
        right_side.pack(side="right", fill="both", padx=(8, 0))
        right_side.pack_propagate(False)

        # Search Bar
        search_row = tk.Frame(left_side, bg=Theme.BG)
        search_row.pack(fill="x", pady=(0, 6))

        search_f = tk.Frame(search_row, bg=Theme.SURFACE2, highlightbackground=Theme.BORDER, highlightthickness=1)
        search_f.pack(side="left", fill="x", expand=True)

        s_icon = get_icon_photo("search", size=15, color=Theme.TEXT_DIM)
        s_lbl = tk.Label(search_f, image=s_icon, bg=Theme.SURFACE2, padx=8)
        s_lbl.image = s_icon
        s_lbl.pack(side="left")

        self.video_search_var = tk.StringVar()
        v_entry = tk.Entry(search_f, textvariable=self.video_search_var, fg=Theme.TEXT_DIM, font=FONT_BODY,
                           borderwidth=0, relief="flat", bg=Theme.SURFACE2, insertbackground=Theme.TEXT)
        v_entry.pack(side="left", fill="both", expand=True, ipady=8)
        v_entry.insert(0, "Search YouTube Videos or paste playlist URL…")
        v_entry.bind("<FocusIn>",  lambda e: self.clear_ph(v_entry, "Search YouTube Videos"))
        v_entry.bind("<FocusOut>", lambda e: self.add_ph(v_entry, "Search YouTube Videos or paste playlist URL…"))
        v_entry.bind("<Return>",   lambda e: self.search(self.video_search_var.get(), parent, "video"))

        create_flat_btn(search_row, "Search", icon_name="search", bg=Theme.ACCENT, fg="#ffffff", hover_bg=Theme.ACCENT2,
                        command=lambda: self.search(self.video_search_var.get(), parent, "video"),
                        font=("Segoe UI", 9, "bold")).pack(side="left", padx=(6, 0))

        # Mode and Local Video Bar
        sub_row = tk.Frame(left_side, bg=Theme.BG)
        sub_row.pack(fill="x", pady=(0, 6))

        self.video_mode_videos_btn = create_flat_btn(
            sub_row, "Videos", icon_name="movie", bg=Theme.ACCENT, fg="#ffffff",
            command=lambda: self._set_video_search_mode("videos"), font=("Segoe UI", 8, "bold")
        )
        self.video_mode_videos_btn.pack(side="left", padx=(0, 4))

        self.video_mode_pl_btn = create_flat_btn(
            sub_row, "Playlists", icon_name="queue_music", bg=Theme.SURFACE2, fg=Theme.TEXT_DIM,
            command=lambda: self._set_video_search_mode("playlists"), font=("Segoe UI", 8, "bold")
        )
        self.video_mode_pl_btn.pack(side="left", padx=(0, 10))

        create_flat_btn(sub_row, "Add Local Video", icon_name="folder", bg=Theme.SURFACE2, fg=Theme.TEXT, hover_bg=Theme.BORDER,
                        command=lambda: self.add_local_file("video"), font=("Segoe UI", 8)).pack(side="right")

        # Results Canvas
        results_outer = tk.Frame(left_side, bg=Theme.BORDER, padx=1, pady=1)
        results_outer.pack(fill="both", expand=True, pady=(0, 6))

        results_canvas = tk.Canvas(results_outer, bg=Theme.SURFACE, highlightthickness=0)
        scroll = tk.Scrollbar(results_outer, orient="vertical", command=results_canvas.yview)
        results_frame = tk.Frame(results_canvas, bg=Theme.SURFACE)

        parent.res_window = results_canvas.create_window((0, 0), window=results_frame, anchor="nw")
        results_canvas.bind("<Configure>", lambda e, c=results_canvas, w=parent.res_window: c.itemconfig(w, width=e.width))
        results_canvas.configure(yscrollcommand=scroll.set)
        results_canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        parent.results_canvas = results_canvas
        parent.results_frame  = results_frame
        parent.cached_results = []
        parent.render_index   = 0
        parent.load_more_btn  = None
        self._bind_scroll(results_canvas, results_frame)

        # Single-Row Transfer Queue Below Search Results
        self._build_single_row_queue(left_side)

        # Right Side: Embedded Video Local PSP Management
        self.video_local_panel = LocalMediaManagerPanel(right_side, "video", self._get_drive_path, self.write_log)
        self.video_local_panel.pack(fill="both", expand=True)

    def _set_video_search_mode(self, mode):
        self.video_search_mode = mode
        if mode == "videos":
            self.video_mode_videos_btn.config(bg=Theme.ACCENT, fg="#ffffff")
            self.video_mode_pl_btn.config(bg=Theme.SURFACE2, fg=Theme.TEXT_DIM)
        else:
            self.video_mode_videos_btn.config(bg=Theme.SURFACE2, fg=Theme.TEXT_DIM)
            self.video_mode_pl_btn.config(bg=Theme.ACCENT, fg="#ffffff")

    # ── Single-Row Grid Queue Implementation ──

    def _build_single_row_queue(self, parent):
        q_container = tk.Frame(parent, bg=Theme.BG)
        q_container.pack(fill="x", pady=(4, 0))

        q_hdr = tk.Frame(q_container, bg=Theme.BG)
        q_hdr.pack(fill="x", pady=(0, 4))

        self.q_count_lbl = tk.Label(
            q_hdr, text="Transfer Queue (0 items)",
            font=("Segoe UI", 9, "bold"), fg=Theme.TEXT, bg=Theme.BG
        )
        self.q_count_lbl.pack(side="left")

        clr = create_flat_btn(q_hdr, "Clear All", icon_name="delete", bg=Theme.SURFACE2, fg=Theme.TEXT_DIM,
                              hover_bg=Theme.ERROR, command=self.clear_queue, font=("Segoe UI", 8))
        clr.pack(side="right")

        q_outer = tk.Frame(q_container, bg=Theme.BORDER, padx=1, pady=1, height=92)
        q_outer.pack(fill="x")
        q_outer.pack_propagate(False)

        q_canvas = tk.Canvas(q_outer, bg=Theme.SURFACE, highlightthickness=0, height=88)
        q_scroll = ttk.Scrollbar(q_outer, orient="horizontal", command=q_canvas.xview)
        q_frame = tk.Frame(q_canvas, bg=Theme.SURFACE, height=84)

        q_win = q_canvas.create_window((0, 0), window=q_frame, anchor="nw")
        q_frame.bind("<Configure>", lambda e, c=q_canvas: c.configure(scrollregion=c.bbox("all")))
        q_canvas.configure(xscrollcommand=q_scroll.set)

        q_canvas.pack(side="top", fill="both", expand=True)
        q_scroll.pack(side="bottom", fill="x")

        # Allow horizontal scroll with mouse wheel
        def _h_scroll(event, c=q_canvas):
            if event.num == 4:
                c.xview_scroll(-1, "units")
            elif event.num == 5:
                c.xview_scroll(1, "units")
            else:
                c.xview_scroll(int(-1 * (event.delta / 120)), "units")

        q_canvas.bind("<MouseWheel>", _h_scroll)
        q_canvas.bind("<Button-4>", _h_scroll)
        q_canvas.bind("<Button-5>", _h_scroll)

        if not hasattr(self, '_queue_widgets'):
            self._queue_widgets = []
        self._queue_widgets.append((q_canvas, q_frame))

        self._render_queue_empty_state(q_frame)

    def _render_queue_empty_state(self, frame):
        empty_lbl = tk.Label(
            frame, text="Queue is empty. Search above or add local files to transfer.",
            font=FONT_SMALL, fg=Theme.TEXT_DIM, bg=Theme.SURFACE, padx=16, pady=26
        )
        empty_lbl.pack(side="left")

    def _refresh_all_queue_views(self):
        count = len(self.queue)
        self._active_marquees = []

        for c, f in getattr(self, '_queue_widgets', []):
            for w in f.winfo_children():
                w.destroy()

            if not self.queue:
                self._render_queue_empty_state(f)
            else:
                for q_data in self.queue:
                    self._create_queue_card(f, q_data)

            f.update_idletasks()
            c.configure(scrollregion=c.bbox("all"))

        # Update count label across headers
        self.q_count_lbl.config(text=f"Transfer Queue ({count} item{'s' if count != 1 else ''})")
        self._update_footer_progress_visibility()

    def _update_footer_progress_visibility(self):
        count = len(self.queue)
        if count > 1:
            self.log_ticker_lbl.pack_forget()
            self._queue_prog_lbl.pack(side="left", padx=(0, 8))
            self.mini_queue_bar.pack(side="right")
        else:
            self._queue_prog_lbl.pack_forget()
            self.mini_queue_bar.pack_forget()
            self.log_ticker_lbl.pack(side="right")

    def _create_queue_card(self, parent_row, q_data):
        card = tk.Frame(parent_row, bg=Theme.SURFACE2, highlightbackground=Theme.BORDER,
                        highlightthickness=1, width=225, height=80)
        card.pack(side="left", padx=4, pady=2)
        card.pack_propagate(False)

        # Left: Square Thumbnail Box
        thumb_f = tk.Frame(card, bg=Theme.SURFACE, width=54, height=54,
                           highlightbackground=Theme.BORDER, highlightthickness=1)
        thumb_f.pack(side="left", padx=(6, 5), pady=11)
        thumb_f.pack_propagate(False)

        vector_icon_name = {"audio": "music_note", "video": "movie", "playlist": "queue_music", "video_playlist": "queue_music"}.get(q_data['type'], "music_note")

        if q_data.get('pil_image'):
            try:
                photo = ImageTk.PhotoImage(q_data['pil_image'].resize((52, 52), Image.Resampling.LANCZOS))
                self.photo_references.append(photo)
                tl = tk.Label(thumb_f, image=photo, bg=Theme.SURFACE)
                tl.image = photo
                tl.pack(fill="both", expand=True)
            except Exception:
                ph = get_icon_photo(vector_icon_name, size=24, color=Theme.TEXT_DIM)
                tl = tk.Label(thumb_f, image=ph, bg=Theme.SURFACE)
                tl.image = ph
                tl.pack(fill="both", expand=True)
        else:
            ph = get_icon_photo(vector_icon_name, size=24, color=Theme.TEXT_DIM)
            tl = tk.Label(thumb_f, image=ph, bg=Theme.SURFACE)
            tl.image = ph
            tl.pack(fill="both", expand=True)

        # Right Controls: Remove X and Status badge
        rt_f = tk.Frame(card, bg=Theme.SURFACE2)
        rt_f.pack(side="right", padx=(2, 6), pady=6)

        rm_icon = get_icon_photo("close", size=13, color=Theme.TEXT_DIM)
        rm_lbl = tk.Label(rt_f, image=rm_icon, bg=Theme.SURFACE2, cursor="hand2")
        rm_lbl.image = rm_icon
        rm_lbl.pack(anchor="ne")

        def _on_rm_enter(e):
            red_ic = get_icon_photo("close", size=13, color=Theme.ERROR)
            rm_lbl.config(image=red_ic)
            rm_lbl.image = red_ic

        def _on_rm_leave(e):
            dim_ic = get_icon_photo("close", size=13, color=Theme.TEXT_DIM)
            rm_lbl.config(image=dim_ic)
            rm_lbl.image = dim_ic

        rm_lbl.bind("<Enter>", _on_rm_enter)
        rm_lbl.bind("<Leave>", _on_rm_leave)
        rm_lbl.bind("<Button-1>", lambda e, q=q_data: (not self.is_processing) and self.remove_from_queue(q))

        status_cvs = tk.Canvas(rt_f, bg=Theme.SURFACE2, width=22, height=22, highlightthickness=0, cursor="hand2")
        status_cvs.pack(anchor="se", pady=(8, 0))
        draw_status_indicator(status_cvs, q_data['status'])
        q_data.setdefault('status_canvases', []).append(status_cvs)

        def _on_status_click(q=q_data):
            if q.get('status') == 'error':
                msg = q.get('error_msg', 'Unknown processing error.')
                item_title = q.get('title', 'Unknown')
                err_text = f"Item: {item_title}\n\nError Details:\n{msg}\n\nCheck Activity Logs for traceback."
                messagebox.showerror('Item Error Details', err_text, parent=self.root)
        status_cvs.bind("<Button-1>", lambda e: _on_status_click())

        # Center: Slow Rotating Marquee Title & Format Badge
        mid_f = tk.Frame(card, bg=Theme.SURFACE2)
        mid_f.pack(side="left", fill="both", expand=True, pady=6)

        marquee = MarqueeLabel(mid_f, text=q_data['title'], font=("Segoe UI", 9, "bold"),
                               fg=Theme.TEXT, bg=Theme.SURFACE2, height=22, width=115)
        marquee.pack(fill="x")
        self._active_marquees.append(marquee)

        sub_text = f"{q_data['type'].upper()} · {q_data.get('formatted_time', '')}"
        meta_lbl = tk.Label(mid_f, text=sub_text, font=("Segoe UI", 7), fg=Theme.TEXT_DIM, bg=Theme.SURFACE2, anchor="w")
        meta_lbl.pack(fill="x", pady=(3, 0))

    # ── Log & Preferences ──

    def write_log(self, message):
        t_str = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{t_str}] › {message}"
        self.log_history.append(line)
        try:
            log_path = os.path.join(os.path.expanduser("~"), ".psp_media_suite.log")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

        def _update():
            if hasattr(self, 'log_ticker_lbl') and self.log_ticker_lbl.winfo_exists():
                self.log_ticker_lbl.config(text=f"› {message}")
                self.log_ticker_lbl.full_text = message
        try:
            self.root.after(0, _update)
        except Exception:
            pass

    def show_activity_log_window(self):
        win = tk.Toplevel(self.root)
        win.title("Activity & System Logs")
        win.geometry("720x460")
        win.configure(bg=Theme.SURFACE)
        win.transient(self.root)

        tk.Frame(win, bg=Theme.ACCENT, height=3).pack(fill="x")

        hdr = tk.Frame(win, bg=Theme.SURFACE)
        hdr.pack(fill="x", padx=12, pady=(10, 6))

        tk.Label(hdr, text="Activity & System Logs", font=("Segoe UI", 11, "bold"),
                 fg=Theme.TEXT, bg=Theme.SURFACE).pack(side="left")

        def _clear_logs():
            self.log_history.clear()
            txt.config(state="normal")
            txt.delete("1.0", tk.END)
            txt.config(state="disabled")

        def _copy_logs():
            self.root.clipboard_clear()
            self.root.clipboard_append("\n".join(self.log_history))
            messagebox.showinfo("Copied", "Logs copied to clipboard.", parent=win)

        create_flat_btn(hdr, "Copy All", icon_name="copy", bg=Theme.SURFACE2, fg=Theme.TEXT,
                        hover_bg=Theme.BORDER, command=_copy_logs, font=("Segoe UI", 8)).pack(side="right")
        create_flat_btn(hdr, "Clear", icon_name="delete", bg=Theme.SURFACE2, fg=Theme.TEXT_DIM,
                        hover_bg=Theme.BORDER, command=_clear_logs, font=("Segoe UI", 8)).pack(side="right", padx=(0, 6))

        txt_frame = tk.Frame(win, bg=Theme.SURFACE)
        txt_frame.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        txt = tk.Text(txt_frame, wrap="word", bg="#0a0a0d", fg=Theme.TEXT, font=FONT_MONO,
                      padx=10, pady=10, insertbackground=Theme.ACCENT, selectbackground=Theme.ACCENT2, borderwidth=0)
        scrollbar = ttk.Scrollbar(txt_frame, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=scrollbar.set)
        txt.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        txt.insert(tk.END, "\n".join(self.log_history))
        txt.see(tk.END)
        txt.config(state="disabled")

    def update_progress(self, val=None):
        if val is not None:
            self.current_progress = val
            if val >= 100:
                self._prog_label.config(text="Transfer Complete", fg=Theme.SUCCESS)
                self.root.after(2000, lambda: self.update_progress(0))
            elif val == 0:
                self._prog_label.config(text="", fg=Theme.TEXT_DIM)
            else:
                self._prog_label.config(text=f"Processing… {int(val)}%", fg=Theme.ACCENT)
            self.progress_bar.update_progress(val)

    def _animate(self):
        # 1. PS3 / PSP XMB fluid wave animation
        self.banner.tick_animation()
        # 2. Pulsating glowing progress bar
        self.progress_bar.tick_pulse()
        # 3. Slow rotating text tickers for queue cards
        for m in getattr(self, '_active_marquees', []):
            if m.winfo_exists():
                m.tick()
        self.root.after(40, self._animate)

    # ── Drive & Tab Management ──

    def scan_usb(self):
        self.drives, unique = scan_psp_drives()
        self._last_drives_unique = unique
        self.drive_combo['values'] = unique
        if unique:
            self.drive_combo.current(0)
            self.write_log(f"Found PSP drive: {unique[0]}")
        else:
            self.drive_combo.set("No PSP Drive Found")
            self.write_log("No PSP drive detected. Connect your PSP in USB mode.")
        self._on_drive_changed()

    def _poll_drives(self):
        try:
            drives, unique = scan_psp_drives()
            if unique != getattr(self, '_last_drives_unique', None):
                self._last_drives_unique = unique
                self.drives = drives
                self.drive_combo['values'] = unique
                if unique:
                    current = self.drive_combo.get()
                    if current not in unique:
                        self.drive_combo.current(0)
                        self.write_log(f"PSP connected: {unique[0]}")
                else:
                    self.drive_combo.set("No PSP Drive Found")
                    self.write_log("PSP disconnected.")
                self._on_drive_changed()
        except Exception:
            pass
        self.root.after(2000, self._poll_drives)

    def _on_drive_changed(self):
        if hasattr(self, 'music_local_panel'):
            self.music_local_panel.refresh()
        if hasattr(self, 'video_local_panel'):
            self.video_local_panel.refresh()

    def _get_drive_path(self):
        return self.drives.get(self.drive_combo.get())

    def switch_tab(self, tab_id):
        self.active_tab = tab_id
        for frame in [self.tab_music, self.tab_video]:
            frame.pack_forget()
        {"audio": self.tab_music, "video": self.tab_video}[tab_id].pack(fill="both", expand=True)
        for tid, btn in self._tab_btns.items():
            if tid == tab_id:
                btn.config(bg=Theme.ACCENT, fg="#ffffff")
            else:
                btn.config(bg=Theme.SURFACE2, fg=Theme.TEXT_DIM)

    # ── Search & Results ──

    def clear_ph(self, entry, prefix):
        if entry.get().startswith(prefix):
            entry.delete(0, tk.END)
            entry.config(fg=Theme.TEXT)

    def add_ph(self, entry, placeholder):
        if not entry.get():
            entry.insert(0, placeholder)
            entry.config(fg=Theme.TEXT_DIM)

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

    def search(self, q, parent, media_type):
        if not q or q.startswith("Search YouTube"):
            return
        for w in parent.results_frame.winfo_children():
            w.destroy()
        parent.cached_results = []
        parent.render_index = 0
        self.update_progress(15)
        self.write_log(f"Searching: {q[:50]}…")

        if media_type == "audio":
            actual_type = "playlist" if self.music_search_mode == "playlists" else "audio"
        else:
            actual_type = "video_playlist" if getattr(self, 'video_search_mode', 'videos') == "playlists" else "video"
        threading.Thread(target=self._search_thread, args=(q, parent, actual_type), daemon=True).start()

    def _search_thread(self, q, parent, media_type):
        try:
            parent.cached_results = search_youtube(q, browser=self.selected_browser, max_results=24)
            self.root.after(0, lambda: self.trigger_load_chunk(parent, media_type))
        except Exception as e:
            self.root.after(0, lambda: self.update_progress(0))
            self.root.after(0, lambda e_msg=str(e): self.write_log(f"Search failed: {e_msg}"))

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
                url = f"https://www.youtube.com/playlist?list={vid_id}" if r.get('_type') == 'playlist' or vid_id.startswith(('PL', 'OL', 'RD')) else f"https://www.youtube.com/watch?v={vid_id}"
                if "watch?v=PL" in url or "watch?v=OL" in url:
                    url = url.replace("watch?v=", "playlist?list=")
            r['url'] = url
            thumb_url = r.get('thumbnail') or (r['thumbnails'][-1].get('url') if r.get('thumbnails') else None)
            r['raw_thumb_url'] = thumb_url
            r['pil_image'] = fetch_thumbnail_preview(thumb_url) if thumb_url else None
            r['formatted_time'] = format_time(r.get('duration', 0))
        self.root.after(0, lambda: self.render_chunk(chunk, parent, media_type))

    def render_chunk(self, chunk, parent, media_type):
        btn_map = {
            "audio": ("Add Music", Theme.ACCENT, "#ffffff"),
            "video": ("Add Video", Theme.ACCENT2, "#ffffff"),
            "playlist": ("Add Playlist", "#8b5cf6", "#ffffff"),
            "video_playlist": ("Add Video Playlist", "#8b5cf6", "#ffffff")
        }
        btn_text, btn_bg, btn_fg = btn_map.get(media_type, ("Add", Theme.ACCENT, "#ffffff"))

        for item in chunk:
            if not item.get('url'):
                continue
            row = tk.Frame(parent.results_frame, bg=Theme.SURFACE, height=58)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)
            row.bind("<Enter>", lambda e, f=row: f.config(bg=Theme.SURFACE2))
            row.bind("<Leave>", lambda e, f=row: f.config(bg=Theme.SURFACE))

            # Square thumbnail container
            thumb_box = tk.Frame(row, bg=Theme.SURFACE2, width=64, height=44,
                                 highlightbackground=Theme.BORDER, highlightthickness=1)
            thumb_box.pack(side="left", padx=(8, 8), pady=6)
            thumb_box.pack_propagate(False)

            if item.get('pil_image'):
                photo = ImageTk.PhotoImage(item['pil_image'])
                self.photo_references.append(photo)
                tl = tk.Label(thumb_box, image=photo, bg=Theme.SURFACE2)
                tl.image = photo
                tl.pack(fill="both", expand=True)
            else:
                ic_name = "movie" if media_type == "video" else "music_note"
                ph = get_icon_photo(ic_name, size=20, color=Theme.TEXT_DIM)
                tl = tk.Label(thumb_box, image=ph, bg=Theme.SURFACE2)
                tl.image = ph
                tl.pack(fill="both", expand=True)

            info_f = tk.Frame(row, bg=Theme.SURFACE)
            info_f.pack(side="left", fill="both", expand=True, pady=6)
            info_f.bind("<Enter>", lambda e, f=row: f.config(bg=Theme.SURFACE2))
            info_f.bind("<Leave>", lambda e, f=row: f.config(bg=Theme.SURFACE))

            tk.Label(info_f, text=item.get('title', 'Unknown')[:56], bg=Theme.SURFACE, fg=Theme.TEXT, font=FONT_BODY, anchor="w").pack(fill="x")
            tk.Label(info_f, text=item['formatted_time'], bg=Theme.SURFACE, fg=Theme.TEXT_DIM, font=FONT_SMALL, anchor="w").pack(fill="x")

            add_btn = create_flat_btn(row, btn_text, icon_name="add", bg=btn_bg, fg=btn_fg, hover_bg=Theme.ACCENT2,
                                      command=lambda i=item, mt=media_type: self.add_to_queue(i, mt),
                                      font=("Segoe UI", 9, "bold"), padx=12, pady=6)
            add_btn.pack(side="right", padx=10)

        parent.render_index += 8
        if parent.render_index < len(parent.cached_results):
            lm = create_flat_btn(parent.results_frame, "Load More Results", icon_name="arrow_down",
                                 bg=Theme.SURFACE2, fg=Theme.TEXT, hover_bg=Theme.BORDER,
                                 command=lambda: self.trigger_load_chunk(parent, media_type),
                                 font=("Segoe UI", 8, "bold"), padx=18, pady=6)
            lm.pack(pady=10)
            parent.load_more_btn = lm

        self.root.update_idletasks()
        parent.results_canvas.configure(scrollregion=parent.results_canvas.bbox("all"))
        self.update_progress(100)

    # ── Queue Operations ──

    def add_to_queue(self, item, media_type):
        now = time.time()
        if hasattr(self, '_last_add_url') and self._last_add_url == item['url'] and now - getattr(self, '_last_add_time', 0) < 0.6:
            return
        self._last_add_url = item['url']
        self._last_add_time = now

        q_data = {
            'status': 'pending',
            'type': media_type,
            'url': item['url'],
            'title': item['title'],
            'thumb': item.get('raw_thumb_url'),
            'pil_image': item.get('pil_image'),
            'formatted_time': item.get('formatted_time', ''),
            'is_local': item.get('is_local', False),
            'status_canvases': []
        }
        self.queue.append(q_data)
        self._refresh_all_queue_views()
        self.write_log(f"Queued: {item['title'][:40]}")

    def remove_from_queue(self, q_data):
        if q_data in self.queue:
            self.queue.remove(q_data)
        self._refresh_all_queue_views()

    def clear_queue(self):
        if self.is_processing:
            return
        self.queue.clear()
        self._refresh_all_queue_views()

    def add_local_file(self, media_type):
        ft = [("Audio Files", "*.mp3 *.ogg *.opus *.m4a *.wav")] if media_type == "audio" else [("Video Files", "*.mp4 *.mkv *.avi *.mov *.webm")]
        for path in filedialog.askopenfilenames(title=f"Select Local {media_type.capitalize()}", filetypes=ft):
            name_no_ext = os.path.splitext(os.path.basename(path))[0]
            self.add_to_queue({
                'title': f"(Local) {name_no_ext}",
                'url': path,
                'is_local': True,
                'pil_image': None,
                'formatted_time': 'Local',
                'raw_thumb_url': None
            }, media_type)

    def pulse_item(self, item, toggle=False):
        if item.get('status') != 'processing':
            return
        for cvs in item.get('status_canvases', []):
            try:
                draw_status_indicator(cvs, "processing")
            except Exception:
                pass
        self.root.after(600, self.pulse_item, item, not toggle)

    # ── USB Processing Worker ──

    def process_queue(self):
        drive_name = self.drive_combo.get()
        if drive_name not in self.drives:
            messagebox.showwarning("No Drive", "Please select a valid PSP drive first.")
            return
        if not self.queue:
            messagebox.showinfo("Queue Empty", "Add some items to the queue first.")
            return

        self.is_processing = True
        self.send_btn.set_state("PROCESSING…", "processing")
        self._update_footer_progress_visibility()
        threading.Thread(target=self._process_queue, args=(self.drives[drive_name],), daemon=True).start()

    def _process_queue(self, drive_path):
        ff_path = get_ffmpeg_path()
        total = len(self.queue)

        for i, item in enumerate(self.queue):
            if item['status'] == 'success':
                continue

            queue_pct = int((i / total) * 100)
            self.root.after(0, lambda qp=queue_pct, idx=i: self._update_queue_progress_ui(idx, total, qp))
            self.root.after(0, lambda msg=f"Processing: {item['title'][:40]}": self.write_log(msg))

            raw_name = os.path.splitext(item['title'])[0] if item.get('is_local') else item['title']
            clean_name = clean_filename(raw_name, 100)
            item['status'] = 'processing'
            self.root.after(0, lambda it=item: self.pulse_item(it))

            cleanup_temp_files(".")

            try:
                if item['type'] == 'playlist':
                    target_dir = os.path.join(drive_path, "MUSIC")
                    playlist_dir = os.path.join(drive_path, "PSP", "PLAYLIST", "MUSIC")
                    os.makedirs(target_dir, exist_ok=True)
                    os.makedirs(playlist_dir, exist_ok=True)
                    m3u8_lines = []

                    self.root.after(0, lambda: self._prog_label.config(text=f"Fetching Playlist: {clean_name[:28]}…", fg=Theme.ACCENT))
                    opts = get_ydl_opts(browser=self.selected_browser, quiet=True, extract_flat=True)
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        entries = ydl.extract_info(item['url'], download=False).get('entries', [])

                    for ei, entry in enumerate(entries):
                        if not entry:
                            continue
                        entry_url = entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
                        entry_title = entry.get('title', f"Track {ei + 1}")
                        clean_en = clean_filename(entry_title, 100)

                        self.root.after(0, lambda t=entry_title: self.write_log(f"  ↳ {t[:30]}"))
                        self.root.after(0, lambda t=entry_title: self._prog_label.config(text=f"Downloading: {t[:28]}…", fg=Theme.ACCENT))

                        dl_opts = get_ydl_opts(
                            browser=self.selected_browser,
                            quiet=True,
                            extract_flat=False,
                            format='bestaudio/best',
                            ffmpeg_location=ff_path,
                            outtmpl='temp_raw.%(ext)s',
                            nopart=True,
                            continuedl=False,
                            postprocessors=[{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
                            postprocessor_args=['-map_metadata', '-1']
                        )

                        try:
                            with yt_dlp.YoutubeDL(dl_opts) as ydl2:
                                einfo = ydl2.extract_info(entry_url, download=True)
                            img = get_best_thumbnail(einfo, entry.get('thumbnail'))
                            if img:
                                try:
                                    crop_and_save_cover(img, "cover.jpg")
                                except Exception:
                                    pass

                            apply_mp3_tags(
                                "temp_raw.mp3",
                                entry_title,
                                "YouTube Audio",
                                item['title'],
                                "cover.jpg" if os.path.exists("cover.jpg") else None
                            )
                            shutil.move("temp_raw.mp3", os.path.join(target_dir, clean_en + ".mp3"))
                            m3u8_lines.append(f"\\MUSIC\\{clean_en}.mp3")
                        except Exception as e:
                            self.root.after(0, lambda err=str(e): self.write_log(f"  Entry failed: {err[:40]}"))

                    if m3u8_lines:
                        pl_filename = clean_filename(item['title'], 100) + ".m3u8"
                        with open(os.path.join(playlist_dir, pl_filename), "w", encoding="utf-8") as f:
                            f.write("\n".join(m3u8_lines))
                    item['status'] = 'success'
                    self.root.after(0, lambda it=item: self._update_item_canvases(it, "success"))

                elif item['type'] == 'video_playlist':
                    target_dir = os.path.join(drive_path, "VIDEO")
                    playlist_dir = os.path.join(drive_path, "PSP", "PLAYLIST", "VIDEO")
                    os.makedirs(target_dir, exist_ok=True)
                    os.makedirs(playlist_dir, exist_ok=True)
                    m3u8_lines = []

                    self.root.after(0, lambda: self._prog_label.config(text=f"Fetching Video Playlist: {clean_name[:24]}…", fg=Theme.ACCENT))
                    opts = get_ydl_opts(browser=self.selected_browser, quiet=True, extract_flat=True)
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        entries = ydl.extract_info(item['url'], download=False).get('entries', [])

                    for ei, entry in enumerate(entries):
                        if not entry:
                            continue
                        entry_url = entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
                        entry_title = entry.get('title', f"Video {ei + 1}")
                        clean_en = clean_filename(entry_title, 100)

                        self.root.after(0, lambda t=entry_title: self.write_log(f"  ↳ Video: {t[:30]}"))
                        self.root.after(0, lambda t=entry_title: self._prog_label.config(text=f"Downloading Video: {t[:24]}…", fg=Theme.ACCENT))

                        dl_opts = get_ydl_opts(
                            browser=self.selected_browser,
                            quiet=True,
                            extract_flat=False,
                            format='bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                            ffmpeg_location=ff_path,
                            outtmpl='temp_raw.%(ext)s',
                            nopart=True,
                            continuedl=False
                        )

                        try:
                            with yt_dlp.YoutubeDL(dl_opts) as ydl2:
                                einfo = ydl2.extract_info(entry_url, download=True)
                            img = get_best_thumbnail(einfo, entry.get('thumbnail'))
                            raw_file = next((f for f in os.listdir(".") if f.startswith("temp_raw.") and not f.endswith(".mp3")), None)
                            if raw_file:
                                self.root.after(0, lambda: self.write_log("Converting to PSP format (H.264 480×272)…"))
                                self.root.after(0, lambda: self._prog_label.config(text="Converting to PSP MP4 (480×272)…", fg=Theme.ACCENT))
                                transcode_video_to_psp(raw_file, "temp.mp4")

                            if img:
                                try:
                                    crop_and_save_thm(img, os.path.join(target_dir, clean_en + ".thm"))
                                except Exception as e:
                                    self.root.after(0, lambda err=str(e): self.write_log(f".THM Error: {err[:40]}"))

                            shutil.move("temp.mp4", os.path.join(target_dir, clean_en + ".mp4"))
                            m3u8_lines.append(f"\\VIDEO\\{clean_en}.mp4")
                        except Exception as e:
                            self.root.after(0, lambda err=str(e): self.write_log(f"  Video entry failed: {err[:40]}"))

                        cleanup_temp_files(".")

                    if m3u8_lines:
                        pl_filename = clean_filename(item['title'], 100) + ".m3u8"
                        with open(os.path.join(playlist_dir, pl_filename), "w", encoding="utf-8") as f:
                            f.write("\n".join(m3u8_lines))
                    item['status'] = 'success'
                    self.root.after(0, lambda it=item: self._update_item_canvases(it, "success"))

                elif item['type'] == 'audio':
                    target_dir = os.path.join(drive_path, "MUSIC")
                    os.makedirs(target_dir, exist_ok=True)

                    if item.get('is_local'):
                        self.root.after(0, lambda: self._prog_label.config(text=f"Transcoding: {clean_name[:28]}…", fg=Theme.ACCENT))
                        transcode_local_audio(item['url'], "temp_raw.mp3")
                    else:
                        self.root.after(0, lambda: self._prog_label.config(text=f"Downloading: {clean_name[:28]}…", fg=Theme.ACCENT))
                        opts = get_ydl_opts(
                            browser=self.selected_browser,
                            quiet=True,
                            extract_flat=False,
                            format='bestaudio/best',
                            ffmpeg_location=ff_path,
                            outtmpl='temp_raw.%(ext)s',
                            nopart=True,
                            continuedl=False,
                            postprocessors=[{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
                            postprocessor_args=['-map_metadata', '-1']
                        )
                        with yt_dlp.YoutubeDL(opts) as ydl:
                            info_dict = ydl.extract_info(item['url'], download=True)
                        img = get_best_thumbnail(info_dict, item.get('thumb'))
                        if img:
                            try:
                                crop_and_save_cover(img, "cover.jpg")
                            except Exception:
                                pass

                    self.root.after(0, lambda: self._prog_label.config(text=f"Tagging & Copying: {clean_name[:26]}…", fg=Theme.ACCENT))
                    apply_mp3_tags(
                        "temp_raw.mp3",
                        item["title"],
                        "YouTube Audio" if not item.get('is_local') else "Local Audio",
                        "PSP Media Suite",
                        "cover.jpg" if os.path.exists("cover.jpg") else None
                    )
                    shutil.move("temp_raw.mp3", os.path.join(target_dir, clean_name + ".mp3"))
                    item['status'] = 'success'
                    self.root.after(0, lambda it=item: self._update_item_canvases(it, "success"))

                else:  # video
                    target_dir = os.path.join(drive_path, "VIDEO")
                    os.makedirs(target_dir, exist_ok=True)
                    img = None

                    if item.get('is_local'):
                        self.root.after(0, lambda: self._prog_label.config(text=f"Transcoding Video: {clean_name[:24]}…", fg=Theme.ACCENT))
                        transcode_video_to_psp(item['url'], "temp.mp4")
                        try:
                            extract_video_frame(item['url'], "temp_thumb.jpg")
                            if os.path.exists("temp_thumb.jpg"):
                                img = Image.open("temp_thumb.jpg")
                        except Exception:
                            pass
                    else:
                        self.root.after(0, lambda: self._prog_label.config(text=f"Downloading Video: {clean_name[:24]}…", fg=Theme.ACCENT))
                        opts = get_ydl_opts(
                            browser=self.selected_browser,
                            quiet=True,
                            extract_flat=False,
                            format='bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                            ffmpeg_location=ff_path,
                            outtmpl='temp_raw.%(ext)s',
                            nopart=True,
                            continuedl=False
                        )
                        with yt_dlp.YoutubeDL(opts) as ydl:
                            info_dict = ydl.extract_info(item['url'], download=True)
                        img = get_best_thumbnail(info_dict, item.get('thumb'))
                        raw_file = next((f for f in os.listdir(".") if f.startswith("temp_raw.") and not f.endswith(".mp3")), None)
                        if raw_file:
                            self.root.after(0, lambda: self.write_log("Converting to PSP format (H.264 480×272)…"))
                            self.root.after(0, lambda: self._prog_label.config(text="Converting to PSP MP4 (480×272)…", fg=Theme.ACCENT))
                            transcode_video_to_psp(raw_file, "temp.mp4")

                    if img:
                        try:
                            crop_and_save_thm(img, os.path.join(target_dir, clean_name + ".thm"))
                        except Exception as e:
                            self.root.after(0, lambda err=str(e): self.write_log(f".THM Error: {err[:40]}"))

                    self.root.after(0, lambda: self._prog_label.config(text="Copying Video to PSP…", fg=Theme.ACCENT))
                    shutil.move("temp.mp4", os.path.join(target_dir, clean_name + ".mp4"))
                    item['status'] = 'success'
                    self.root.after(0, lambda it=item: self._update_item_canvases(it, "success"))

            except Exception as e:
                err_msg = str(e)
                import traceback
                tb = traceback.format_exc()
                self.root.after(0, lambda m=f"Failed: {clean_name[:25]} ({err_msg[:45]})": self.write_log(m))
                try:
                    log_file = os.path.join(os.path.expanduser("~"), ".psp_media_suite.log")
                    with open(log_file, "a", encoding="utf-8") as lf:
                        lf.write('\n--- ERROR TRACEBACK for ' + str(item.get('title')) + ' ---\n' + tb + '\n-------------------------\n')
                except Exception:
                    pass
                item['status'] = 'error'
                item['error_msg'] = err_msg
                self.root.after(0, lambda it=item: self._update_item_canvases(it, "error"))

            cleanup_temp_files(".")

        if sys.platform == "darwin":
            try:
                subprocess.run(["dot_clean", "-fm", drive_path], capture_output=True)
            except Exception:
                pass

        self.is_processing = False
        has_errors = any(it.get('status') == 'error' for it in self.queue)
        if has_errors:
            self.root.after(0, lambda: self.update_progress(0))
            self.root.after(0, lambda: self.send_btn.set_state("SEND QUEUE VIA USB", "normal"))
            self.root.after(0, lambda: self.write_log("Finished with errors. Check queue badges or Activity Logs."))
            self.root.after(0, lambda: self._prog_label.config(text="Finished with errors", fg=Theme.ERROR))
            self.root.after(0, self._on_drive_changed)
            self.root.after(0, lambda: messagebox.showwarning("Sync Finished with Errors", "Some items failed to download or sync.\nClick the red cross badges in the queue or open Logs in the menu."))
        else:
            self.root.after(0, lambda: self.update_progress(100))
            self.root.after(0, lambda: self.mini_queue_bar.update_progress(100))
            self.root.after(0, lambda: self._queue_prog_lbl.config(text=f"Queue: {total} of {total} · 100%"))
            self.root.after(0, lambda: self.send_btn.set_state("SEND QUEUE VIA USB", "normal"))
            self.root.after(0, lambda: self.write_log("All done! Media synced to PSP successfully."))
            self.root.after(0, lambda: self._prog_label.config(text="All Media Synced Successfully", fg=Theme.SUCCESS))
            self.root.after(0, self._on_drive_changed)
            self.root.after(0, lambda: messagebox.showinfo("Done!", "All items processed and synced to PSP."))

    def _update_queue_progress_ui(self, index, total, queue_pct):
        self.update_progress(queue_pct)
        self.mini_queue_bar.update_progress(queue_pct)
        self._queue_prog_lbl.config(text=f"Queue: Item {index + 1} of {total} · {queue_pct}%")

    def _update_item_canvases(self, item, status):
        for cvs in item.get('status_canvases', []):
            try:
                draw_status_indicator(cvs, status)
            except Exception:
                pass

    # ── Dialogs ──

    def toggle_server(self):
        if self.web_server.is_running():
            self.web_server.stop()
            self.server_btn.config(text="  Server", fg="#ffffff")
            self.write_log("Web Server stopped.")
        else:
            ip = get_local_ip()
            self.web_server.start()
            self.server_btn.config(text="  Stop Server", fg="#f59e0b")
            self.write_log(f"Server started! Navigate PSP to: http://{ip}:{self.web_server.port}")
            show_server_started_dialog(self.root, ip, self.web_server.port, on_more_info=lambda: show_web_server_info_dialog(self.root))

    def show_about(self):
        def _theme_cb(is_dark):
            self.is_dark_mode = is_dark
            self._save_prefs()

        def _browser_cb(browser):
            self.selected_browser = browser
            self._save_prefs()

        show_about_dialog(
            parent=self.root,
            current_browser=self.selected_browser,
            is_dark_mode=self.is_dark_mode,
            on_theme_change=_theme_cb,
            on_browser_change=_browser_cb,
            on_show_troubleshooter=lambda: show_troubleshooter_dialog(self.root),
            on_show_logs=self.show_activity_log_window
        )
