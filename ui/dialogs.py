import os
import sys
import webbrowser
import requests
import threading
import tkinter as tk
from tkinter import messagebox, ttk, simpledialog
from PIL import Image, ImageTk
from ui.theme import Theme, FONT_BODY, FONT_MONO, FONT_SMALL
from ui.components import create_flat_btn
from core.config import get_resource_path
from core.device import get_music_dir, get_video_dir, get_playlist_dir
from core.media_manager import (
    AUDIO_EXTS,
    VIDEO_EXTS,
    list_media_files,
    rename_media_file,
    delete_media_files,
    open_system_folder,
    list_playlists,
    read_playlist,
    write_playlist,
    song_display_name,
    media_display_name,
    create_playlist,
    rename_playlist,
    delete_playlist,
    list_available_mp3s,
    list_available_videos,
    list_available_media
)

class FileManagerDialog(tk.Toplevel):
    """Dialog for managing music or video files stored locally on the PSP."""

    def __init__(self, parent, drive_path, media_type, on_log=None):
        super().__init__(parent)
        self.drive = drive_path
        self.media_type = media_type
        self.on_log = on_log or (lambda msg: None)

        self.folder = get_music_dir(drive_path) if media_type == "audio" else get_video_dir(drive_path)
        os.makedirs(self.folder, exist_ok=True)
        self.exts = AUDIO_EXTS if media_type == "audio" else VIDEO_EXTS

        title_type = "Music" if media_type == "audio" else "Videos"
        self.title(f"Manage {title_type} on PSP")
        self.geometry("680x520")
        self.configure(bg=Theme.BG)
        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

        self._build_ui()
        self.load_files()

    def _build_ui(self):
        tk.Frame(self, bg=Theme.ACCENT, height=3).pack(fill="x")

        hdr = tk.Frame(self, bg=Theme.BG)
        hdr.pack(fill="x", padx=16, pady=(12, 6))
        ic_name = "music_note" if self.media_type == "audio" else "movie"
        title_type = "Music" if self.media_type == "audio" else "Video"
        tk.Label(hdr, text=f"{title_type} Files on PSP",
                 font=("Segoe UI", 13, "bold"), fg=Theme.TEXT, bg=Theme.BG).pack(side="left")
        tk.Label(hdr, text=self.folder, font=("Segoe UI", 8),
                 fg=Theme.TEXT_DIM, bg=Theme.BG).pack(side="left", padx=(10, 0), pady=(4, 0))

        list_outer = tk.Frame(self, bg=Theme.BORDER, padx=1, pady=1)
        list_outer.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        cols = ("name", "size")
        self.tree = ttk.Treeview(list_outer, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("name", text="File Name")
        self.tree.heading("size", text="Size")
        self.tree.column("name", width=480, anchor="w")
        self.tree.column("size", width=80, anchor="e")

        style = ttk.Style()
        style.configure("Manager.Treeview", background=Theme.SURFACE, fieldbackground=Theme.SURFACE,
                        foreground=Theme.TEXT, rowheight=26, borderwidth=0)
        style.configure("Manager.Treeview.Heading", background=Theme.SURFACE2, foreground=Theme.TEXT, borderwidth=0)
        style.map("Manager.Treeview", background=[("selected", Theme.ACCENT)], foreground=[("selected", "#ffffff")])
        self.tree.configure(style="Manager.Treeview")

        vsb = ttk.Scrollbar(list_outer, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        btn_row = tk.Frame(self, bg=Theme.BG)
        btn_row.pack(fill="x", padx=16, pady=(0, 12))

        actions = [
            ("Rename", self.rename_selected, Theme.ACCENT),
            ("Delete", self.delete_selected, Theme.ERROR),
            ("Open Folder", lambda: open_system_folder(self.folder), Theme.SURFACE2),
            ("Refresh", self.load_files, Theme.SURFACE2)
        ]
        for txt, cmd, col in actions:
            fg_col = "#ffffff" if col not in (Theme.SURFACE2,) else Theme.TEXT
            b = create_flat_btn(btn_row, txt, bg=col, fg=fg_col, hover_bg=Theme.BORDER, command=cmd, font=("Segoe UI", 9, "bold"))
            b.pack(side="left", padx=(0, 8))

    def load_files(self):
        self.tree.delete(*self.tree.get_children())
        files = list_media_files(self.folder, self.exts)
        for fname, size_str in files:
            self.tree.insert("", tk.END, iid=fname, values=(fname, size_str))

    def rename_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select File", "Select a file to rename.", parent=self)
            return
        old_name = sel[0]
        old_base = os.path.splitext(old_name)[0]
        new_base = simpledialog.askstring("Rename", f"New name for:\n{old_name}", initialvalue=old_base, parent=self)
        if not new_base:
            return

        try:
            rename_media_file(self.folder, self.drive, self.media_type, old_name, new_base)
            self.load_files()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        if not messagebox.askyesno("Confirm Delete", f"Delete {len(sel)} file(s)?", parent=self):
            return
        try:
            delete_media_files(self.folder, self.media_type, sel)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)
        self.load_files()

class PlaylistManagerDialog(tk.Toplevel):
    """Dialog for managing .m3u8 playlists and track ordering on the PSP."""

    def __init__(self, parent, drive_path, media_type="audio", on_log=None):
        super().__init__(parent)
        self.drive = drive_path
        self.media_type = media_type
        self.on_log = on_log or (lambda msg: None)

        self.media_dir = get_music_dir(drive_path) if media_type == "audio" else get_video_dir(drive_path)
        self.pl_dir = get_playlist_dir(drive_path, media_type)
        os.makedirs(self.media_dir, exist_ok=True)
        os.makedirs(self.pl_dir, exist_ok=True)

        self.current_pl_name = None

        type_label = "Music" if media_type == "audio" else "Video"
        self.title(f"Manage {type_label} Playlists — PSP Media Suite")
        self.geometry("820x560")
        self.configure(bg=Theme.BG)
        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

        self._build_ui()
        self.load_playlists()

    def _build_ui(self):
        tk.Frame(self, bg=Theme.ACCENT, height=3).pack(fill="x")
        hdr = tk.Frame(self, bg=Theme.BG)
        hdr.pack(fill="x", padx=16, pady=(12, 8))
        type_label = "Music" if self.media_type == "audio" else "Video"
        tk.Label(hdr, text=f"{type_label} Playlist Manager", font=("Segoe UI", 13, "bold"), fg=Theme.TEXT, bg=Theme.BG).pack(side="left")

        panes = tk.Frame(self, bg=Theme.BG)
        panes.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        # Left pane: Playlist list
        left_pane = tk.Frame(panes, bg=Theme.BG, width=240)
        left_pane.pack(side="left", fill="y", padx=(0, 10))
        left_pane.pack_propagate(False)

        tk.Label(left_pane, text="Playlists", font=("Segoe UI", 10, "bold"), fg=Theme.TEXT, bg=Theme.BG).pack(anchor="w", pady=(0, 4))
        pl_list_outer = tk.Frame(left_pane, bg=Theme.BORDER, padx=1, pady=1)
        pl_list_outer.pack(fill="both", expand=True)

        self.pl_listbox = tk.Listbox(pl_list_outer, bg=Theme.SURFACE, fg=Theme.TEXT, font=("Segoe UI", 10),
                                     selectbackground=Theme.ACCENT, selectforeground="#ffffff",
                                     borderwidth=0, highlightthickness=0, activestyle="none")
        pl_scroll = ttk.Scrollbar(pl_list_outer, orient="vertical", command=self.pl_listbox.yview)
        self.pl_listbox.configure(yscrollcommand=pl_scroll.set)
        self.pl_listbox.pack(side="left", fill="both", expand=True)
        pl_scroll.pack(side="right", fill="y")
        self.pl_listbox.bind("<<ListboxSelect>>", self.on_pl_select)

        pl_btn_row = tk.Frame(left_pane, bg=Theme.BG)
        pl_btn_row.pack(fill="x", pady=(6, 0))

        for txt, cmd, col in [("New", self.new_playlist, Theme.ACCENT),
                              ("Rename", self.rename_playlist, Theme.SURFACE2),
                              ("Delete", self.delete_playlist, Theme.ERROR)]:
            fg_col = "#ffffff" if col != Theme.SURFACE2 else Theme.TEXT
            b = create_flat_btn(pl_btn_row, txt, bg=col, fg=fg_col, hover_bg=Theme.BORDER, command=cmd, font=("Segoe UI", 9, "bold"))
            b.pack(side="top", fill="x", pady=3)

        # Right pane: Items in playlist
        right_pane = tk.Frame(panes, bg=Theme.BG)
        right_pane.pack(side="left", fill="both", expand=True)

        self.pl_name_var = tk.StringVar(value="← Select or create a playlist")
        tk.Label(right_pane, textvariable=self.pl_name_var, font=("Segoe UI", 10, "bold"), fg=Theme.TEXT, bg=Theme.BG).pack(anchor="w", pady=(0, 4))

        song_outer = tk.Frame(right_pane, bg=Theme.BORDER, padx=1, pady=1)
        song_outer.pack(fill="both", expand=True)

        self.song_listbox = tk.Listbox(song_outer, bg=Theme.SURFACE, fg=Theme.TEXT, font=("Segoe UI", 10),
                                       selectbackground=Theme.ACCENT, selectforeground="#ffffff",
                                       borderwidth=0, highlightthickness=0, activestyle="none", selectmode="extended")
        song_scroll = ttk.Scrollbar(song_outer, orient="vertical", command=self.song_listbox.yview)
        self.song_listbox.configure(yscrollcommand=song_scroll.set)
        self.song_listbox.pack(side="left", fill="both", expand=True)
        song_scroll.pack(side="right", fill="y")

        song_btn_row = tk.Frame(right_pane, bg=Theme.BG)
        song_btn_row.pack(fill="x", pady=(6, 0))

        item_btn_label = "Add Songs" if self.media_type == "audio" else "Add Videos"
        for txt, cmd, col in [(item_btn_label, self.add_songs, Theme.ACCENT),
                              ("Remove", self.remove_songs, Theme.ERROR),
                              ("Move Up", self.move_up, Theme.SURFACE2),
                              ("Move Down", self.move_down, Theme.SURFACE2)]:
            fg_col = "#ffffff" if col not in (Theme.SURFACE2,) else Theme.TEXT
            b = create_flat_btn(song_btn_row, txt, bg=col, fg=fg_col, hover_bg=Theme.BORDER, command=cmd, font=("Segoe UI", 9, "bold"))
            b.pack(side="left", padx=(0, 6))

    def load_playlists(self):
        self.pl_listbox.delete(0, tk.END)
        for pl in list_playlists(self.pl_dir):
            self.pl_listbox.insert(tk.END, pl)

    def on_pl_select(self, event=None):
        sel = self.pl_listbox.curselection()
        if not sel:
            return
        name = self.pl_listbox.get(sel[0])
        self.current_pl_name = name
        self.pl_name_var.set(f"Songs in: {name}")
        self.load_songs()

    def load_songs(self):
        self.song_listbox.delete(0, tk.END)
        if not self.current_pl_name:
            return
        lines = read_playlist(self.pl_dir, self.current_pl_name)
        for line in lines:
            self.song_listbox.insert(tk.END, song_display_name(line))

    def new_playlist(self):
        name = simpledialog.askstring("New Playlist", "Playlist name:", parent=self)
        if not name:
            return
        name = name.strip()
        ok, err = create_playlist(self.pl_dir, name)
        if not ok:
            messagebox.showwarning("Exists", f"'{name}' already exists.", parent=self)
            return
        self.load_playlists()

    def rename_playlist(self):
        if not self.current_pl_name:
            return
        old = self.current_pl_name
        new = simpledialog.askstring("Rename", "New name:", initialvalue=old, parent=self)
        if not new:
            return
        new = new.strip()
        try:
            rename_playlist(self.pl_dir, old, new)
            self.current_pl_name = new
            self.pl_name_var.set(f"Songs in: {new}")
            self.load_playlists()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def delete_playlist(self):
        if not self.current_pl_name:
            return
        if not messagebox.askyesno("Delete", f"Delete playlist '{self.current_pl_name}'?", parent=self):
            return
        try:
            delete_playlist(self.pl_dir, self.current_pl_name)
            self.current_pl_name = None
            self.pl_name_var.set("← Select or create a playlist")
            self.song_listbox.delete(0, tk.END)
            self.load_playlists()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def add_songs(self):
        if not self.current_pl_name:
            return
        avail = list_available_media(self.media_dir, self.media_type)
        item_label = "songs" if self.media_type == "audio" else "videos"
        folder_label = "MUSIC" if self.media_type == "audio" else "VIDEO"
        if not avail:
            messagebox.showinfo(f"No {item_label.capitalize()}", f"No media files found in PSP {folder_label} folder.", parent=self)
            return

        pick = tk.Toplevel(self)
        pick.title(f"Add {item_label.capitalize()}")
        pick.geometry("460x400")
        pick.configure(bg=Theme.BG)
        pick.transient(self)
        pick.wait_visibility()
        pick.grab_set()

        tk.Label(pick, text=f"Select {item_label} to add:", font=("Segoe UI", 10, "bold"), fg=Theme.TEXT, bg=Theme.BG).pack(padx=16, pady=(12, 4), anchor="w")
        pick_outer = tk.Frame(pick, bg=Theme.BORDER, padx=1, pady=1)
        pick_outer.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        pick_lb = tk.Listbox(pick_outer, bg=Theme.SURFACE, fg=Theme.TEXT, font=("Segoe UI", 10),
                             selectbackground=Theme.ACCENT, selectforeground="#ffffff",
                             borderwidth=0, highlightthickness=0, selectmode="extended")
        pick_sb = ttk.Scrollbar(pick_outer, orient="vertical", command=pick_lb.yview)
        pick_lb.configure(yscrollcommand=pick_sb.set)
        pick_lb.pack(side="left", fill="both", expand=True)
        pick_sb.pack(side="right", fill="y")

        existing = read_playlist(self.pl_dir, self.current_pl_name)
        existing_files = {song_display_name(l).lower() for l in existing}
        for f in avail:
            if f.lower() not in existing_files:
                pick_lb.insert(tk.END, f)

        def confirm_add():
            sel = pick_lb.curselection()
            if not sel:
                pick.destroy()
                return
            lines = read_playlist(self.pl_dir, self.current_pl_name)
            prefix = "\\MUSIC\\" if self.media_type == "audio" else "\\VIDEO\\"
            for idx in sel:
                lines.append(f"{prefix}{pick_lb.get(idx)}")
            write_playlist(self.pl_dir, self.current_pl_name, lines)
            self.load_songs()
            pick.destroy()

        add_row = tk.Frame(pick, bg=Theme.BG)
        add_row.pack(fill="x", padx=16, pady=(0, 12))
        create_flat_btn(add_row, "Add Selected", bg=Theme.ACCENT, fg="#ffffff", hover_bg=Theme.ACCENT2, command=confirm_add, font=("Segoe UI", 10, "bold")).pack(side="left")
        create_flat_btn(add_row, "Cancel", bg=Theme.SURFACE2, fg=Theme.TEXT, hover_bg=Theme.BORDER, command=pick.destroy).pack(side="left", padx=(8, 0))

    def remove_songs(self):
        if not self.current_pl_name:
            return
        sel = self.song_listbox.curselection()
        if not sel:
            return
        lines = read_playlist(self.pl_dir, self.current_pl_name)
        to_remove = {self.song_listbox.get(i).lower() for i in sel}
        new_lines = [l for l in lines if song_display_name(l).lower() not in to_remove]
        write_playlist(self.pl_dir, self.current_pl_name, new_lines)
        self.load_songs()

    def move_up(self):
        sel = self.song_listbox.curselection()
        if not sel or sel[0] == 0:
            return
        lines = read_playlist(self.pl_dir, self.current_pl_name)
        for i in sel:
            if i > 0:
                lines[i - 1], lines[i] = lines[i], lines[i - 1]
        write_playlist(self.pl_dir, self.current_pl_name, lines)
        self.load_songs()
        self.song_listbox.selection_set([i - 1 for i in sel if i > 0])

    def move_down(self):
        sel = self.song_listbox.curselection()
        if not sel or sel[-1] == self.song_listbox.size() - 1:
            return
        lines = read_playlist(self.pl_dir, self.current_pl_name)
        for i in reversed(sel):
            if i < len(lines) - 1:
                lines[i], lines[i + 1] = lines[i + 1], lines[i]
        write_playlist(self.pl_dir, self.current_pl_name, lines)
        self.load_songs()
        self.song_listbox.selection_set([i + 1 for i in sel if i < len(lines) - 1])

def show_about_dialog(parent, current_browser, is_dark_mode, on_theme_change, on_browser_change, on_show_troubleshooter, on_show_logs=None):
    """Displays the About & Preferences modal dialog with direct access to Logs and Troubleshooter."""
    about = tk.Toplevel(parent)
    about.title("Preferences & About")
    about.geometry("340x600")
    about.configure(bg=Theme.SURFACE)
    about.resizable(False, False)
    about.transient(parent)

    tk.Frame(about, bg=Theme.ACCENT, height=3).pack(fill="x")
    inner = tk.Frame(about, bg=Theme.SURFACE)
    inner.pack(fill="both", expand=True, padx=22, pady=16)

    icon_path = get_resource_path("Icon.png")
    if os.path.exists(icon_path):
        try:
            img = Image.open(icon_path).resize((64, 64), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            lbl = tk.Label(inner, image=photo, bg=Theme.SURFACE)
            lbl.image = photo
            lbl.pack(pady=(0, 8))
        except Exception:
            pass

    tk.Label(inner, text="PSP Media Suite", font=("Segoe UI", 13, "bold"), fg=Theme.TEXT, bg=Theme.SURFACE).pack()
    tk.Label(inner, text="v1.7.2  ·  PlayStation Portable Suite", font=("Segoe UI", 8), fg=Theme.TEXT_DIM, bg=Theme.SURFACE).pack(pady=(2, 12))

    # Action Buttons: Activity Logs and Troubleshooter
    if on_show_logs:
        create_flat_btn(inner, "Activity & System Logs", icon_name="article", bg=Theme.ACCENT, fg="#ffffff",
                        hover_bg=Theme.ACCENT2, command=on_show_logs, font=("Segoe UI", 9, "bold")).pack(fill="x", pady=3)

    create_flat_btn(inner, "Connection Troubleshooter", icon_name="settings", bg=Theme.SURFACE2, fg=Theme.TEXT,
                    hover_bg=Theme.BORDER, command=on_show_troubleshooter, font=("Segoe UI", 9)).pack(fill="x", pady=3)

    tk.Frame(inner, bg=Theme.BORDER, height=1).pack(fill="x", pady=10)

    # Appearance
    tk.Label(inner, text="Appearance", font=("Segoe UI", 9, "bold"), fg=Theme.TEXT, bg=Theme.SURFACE).pack(anchor="w")

    dark_var = tk.BooleanVar(value=is_dark_mode)
    def _toggle_theme():
        on_theme_change(dark_var.get())
        messagebox.showinfo("Theme Changed", "Please restart the application to apply the new theme.", parent=about)

    chk = tk.Checkbutton(inner, text="Dark Mode", variable=dark_var, bg=Theme.SURFACE, fg=Theme.TEXT,
                         selectcolor=Theme.SURFACE2, activebackground=Theme.SURFACE,
                         activeforeground=Theme.TEXT, command=_toggle_theme, cursor="hand2")
    chk.pack(anchor="w", pady=(4, 8))

    # YouTube Bot / Age Checks
    tk.Label(inner, text="Bypass YouTube Bot / Age Checks", font=("Segoe UI", 9, "bold"), fg=Theme.TEXT, bg=Theme.SURFACE).pack(anchor="w")
    tk.Label(inner, text="Browser with YouTube login cookies:", font=("Segoe UI", 8),
             fg=Theme.TEXT_DIM, bg=Theme.SURFACE, wraplength=280, justify="left").pack(anchor="w", pady=(2, 4))

    menu_cookie_combo = ttk.Combobox(inner, state="readonly", style="App.TCombobox", font=FONT_BODY)
    menu_cookie_combo['values'] = ["None", "Chrome", "Edge", "Firefox", "Brave", "Safari", "Opera"]
    menu_cookie_combo.set(current_browser)
    menu_cookie_combo.pack(fill="x", pady=(0, 10))

    def _on_browser_changed(e):
        on_browser_change(menu_cookie_combo.get())

    menu_cookie_combo.bind("<<ComboboxSelected>>", _on_browser_changed)

    tk.Frame(inner, bg=Theme.BORDER, height=1).pack(fill="x", pady=8)

    # External links
    links_row = tk.Frame(inner, bg=Theme.SURFACE)
    links_row.pack(fill="x", pady=(0, 10))

    create_flat_btn(links_row, "GitHub", icon_name="public", bg=Theme.SURFACE2, fg=Theme.TEXT,
                    hover_bg=Theme.BORDER, command=lambda: webbrowser.open("https://github.com/vmg265/PSP-Media-Suite"),
                    font=("Segoe UI", 8)).pack(side="left", fill="x", expand=True, padx=(0, 4))

    create_flat_btn(links_row, "Support", icon_name="info", bg=Theme.SURFACE2, fg=Theme.TEXT,
                    hover_bg=Theme.BORDER, command=lambda: webbrowser.open("https://rzp.io/rzp/pFrhgY8"),
                    font=("Segoe UI", 8)).pack(side="right", fill="x", expand=True, padx=(4, 0))

    # Close button at bottom
    create_flat_btn(inner, "Close", icon_name="close", bg=Theme.SURFACE2, fg=Theme.TEXT_DIM,
                    hover_bg=Theme.BORDER, command=about.destroy, font=("Segoe UI", 9)).pack(fill="x", pady=(4, 0))

    # Keyboard shortcut: Escape to close
    about.bind("<Escape>", lambda e: about.destroy())

def show_troubleshooter_dialog(parent):
    """Displays online/offline troubleshooter notes and known fixes."""
    win = tk.Toplevel(parent)
    win.title("Troubleshooter")
    win.geometry("600x420")
    win.configure(bg=Theme.SURFACE)
    win.transient(parent)

    tk.Frame(win, bg=Theme.ACCENT, height=2).pack(fill="x")
    txt = tk.Text(win, wrap="word", bg=Theme.SURFACE, fg=Theme.TEXT, font=FONT_MONO,
                  padx=12, pady=12, insertbackground=Theme.ACCENT, selectbackground=Theme.ACCENT2, borderwidth=0)
    txt.pack(fill="both", expand=True, padx=8, pady=8)

    txt.insert(tk.END, "Loading troubleshooter data from GitHub...\n\n")
    win.update()

    def fetch():
        try:
            url = "https://raw.githubusercontent.com/vmg265/PSP-Media-Suite/main/troubleshooter_box.txt"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                content = response.text
            else:
                content = f"Failed to load. HTTP Status: {response.status_code}"
        except Exception as e:
            content = f"Error reaching GitHub:\n{e}\n\nPlease check your internet connection."
        parent.after(0, lambda: _update(content))

    def _update(content):
        txt.config(state="normal")
        txt.delete(1.0, tk.END)
        txt.insert(tk.END, content)
        txt.config(state="disabled")

    threading.Thread(target=fetch, daemon=True).start()

def show_web_server_info_dialog(parent):
    """Displays full instructions for configuring network / ChromeOS port forwarding."""
    win = tk.Toplevel(parent)
    win.title("Web Server Info")
    win.configure(bg=Theme.SURFACE)
    win.transient(parent)

    try:
        win.state('zoomed')
    except tk.TclError:
        try:
            win.attributes('-zoomed', True)
        except Exception:
            win.attributes('-fullscreen', True)

    win.bind("<Escape>", lambda e: win.destroy())
    tk.Frame(win, bg=Theme.ACCENT, height=2).pack(fill="x")

    txt_frame = tk.Frame(win, bg=Theme.SURFACE)
    txt_frame.pack(fill="both", expand=True, padx=8, pady=8)

    txt = tk.Text(txt_frame, wrap="word", bg=Theme.SURFACE, fg=Theme.TEXT, font=FONT_MONO,
                  padx=12, pady=12, insertbackground=Theme.ACCENT, selectbackground=Theme.ACCENT2, borderwidth=0)
    scrollbar = ttk.Scrollbar(txt_frame, orient="vertical", command=txt.yview)
    txt.configure(yscrollcommand=scrollbar.set)
    txt.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    txt.insert(tk.END, "Loading info from GitHub...\n")
    win.update()

    def fetch():
        try:
            url = "https://raw.githubusercontent.com/vmg265/PSP-Media-Suite/main/web-server-info.txt"
            r = requests.get(url, timeout=5)
            r.raise_for_status()
            content = r.text
        except Exception as e:
            content = f"Failed to load info from GitHub.\n\nError: {e}\n\nPlease check your internet connection."
        parent.after(0, lambda: _update(content))

    def _update(content):
        txt.config(state="normal")
        txt.delete(1.0, tk.END)
        txt.insert(tk.END, content)
        txt.config(state="disabled")

    threading.Thread(target=fetch, daemon=True).start()

def show_server_started_dialog(parent, ip, port, on_more_info):
    """Popup alert shown when the web server is activated."""
    pop = tk.Toplevel(parent)
    pop.title("Server Started")
    pop.geometry("380x200")
    pop.configure(bg=Theme.SURFACE)
    pop.transient(parent)
    pop.wait_visibility()
    pop.grab_set()

    msg = f"Navigate your PSP browser to:\n\nhttp://{ip}:{port}"
    tk.Label(pop, text=msg, font=("Segoe UI", 11, "bold"), bg=Theme.SURFACE, fg=Theme.TEXT).pack(pady=25)

    btn_container = tk.Frame(pop, bg=Theme.SURFACE)
    btn_container.pack(fill="x", side="bottom", pady=15)

    create_flat_btn(btn_container, "More Info", bg=Theme.SURFACE2, fg=Theme.ACCENT, hover_bg=Theme.BORDER,
                    command=on_more_info).pack(pady=(0, 8))
    create_flat_btn(btn_container, "Okay", bg=Theme.ACCENT, fg="#ffffff", hover_bg=Theme.ACCENT2,
                    command=pop.destroy).pack()
