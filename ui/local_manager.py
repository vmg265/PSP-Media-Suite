import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk

from ui.theme import Theme, FONT_BODY, FONT_SMALL
from ui.icons import get_icon_photo
from ui.components import create_flat_btn, draw_rounded_rect
from ui.thumbnail_editor import ThumbnailEditorDialog
from core.device import get_music_dir, get_video_dir, get_playlist_dir
from core.media_manager import (
    AUDIO_EXTS,
    VIDEO_EXTS,
    get_detailed_media_files,
    get_cached_cover,
    sort_media_files,
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

class HoverTooltip:
    """
    Shows a clean floating tooltip displaying full filename and details when hovering over a card or row.
    """
    _active = None

    def __init__(self, widget, full_name, size_str, date_str, media_type):
        self.widget = widget
        self.full_name = full_name
        self.size_str = size_str
        self.date_str = date_str
        self.media_type = media_type
        self.tip_window = None
        self._after_id = None

        self.widget.bind("<Enter>", self._on_enter, add="+")
        self.widget.bind("<Leave>", self._on_leave, add="+")
        self.widget.bind("<Motion>", self._on_motion, add="+")
        self.widget.bind("<ButtonPress>", self._on_leave, add="+")

    @classmethod
    def close_active(cls):
        if cls._active:
            try:
                cls._active.hide_tip()
            except Exception:
                pass
            cls._active = None

    def _on_enter(self, event=None):
        self._cancel()
        self._after_id = self.widget.after(160, self.show_tip)

    def _on_motion(self, event=None):
        if self.tip_window and event:
            x = event.x_root + 15
            y = event.y_root + 18
            self.tip_window.wm_geometry(f"+{x}+{y}")

    def _on_leave(self, event=None):
        self._cancel()
        self.hide_tip()

    def _cancel(self):
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def show_tip(self):
        HoverTooltip.close_active()
        HoverTooltip._active = self

        if self.tip_window or not self.widget.winfo_exists():
            return

        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4

        try:
            screen_w = self.widget.winfo_screenwidth()
            screen_h = self.widget.winfo_screenheight()
        except Exception:
            screen_w, screen_h = 1920, 1080

        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        try:
            tw.attributes("-topmost", True)
        except Exception:
            pass

        frame = tk.Frame(tw, bg="#18181b", highlightbackground=Theme.ACCENT, highlightthickness=1, padx=10, pady=8)
        frame.pack()

        tk.Label(frame, text=self.full_name, font=("Segoe UI", 9, "bold"),
                 fg="#ffffff", bg="#18181b", wraplength=420, justify="left").pack(anchor="w")

        tk.Label(frame, text=f"Size: {self.size_str}   ·   Modified: {self.date_str}",
                 font=("Segoe UI", 8), fg="#a1a1aa", bg="#18181b").pack(anchor="w", pady=(3, 0))

        tw.update_idletasks()
        tw_w = tw.winfo_width()
        tw_h = tw.winfo_height()

        if x + tw_w > screen_w - 12:
            x = screen_w - tw_w - 12
        if y + tw_h > screen_h - 12:
            y = self.widget.winfo_rooty() - tw_h - 4

        tw.wm_geometry(f"+{max(8, x)}+{max(8, y)}")

    def hide_tip(self):
        self._cancel()
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None
        if HoverTooltip._active == self:
            HoverTooltip._active = None


class LocalMediaManagerPanel(tk.Frame):
    """
    Embedded local PSP file & playlist management panel.
    Supports toggleable Grid and List views with cover art, search filtering,
    and multiple sort options. Google Material icons throughout (no emojis).
    """

    def __init__(self, parent, media_type, get_drive_callback, on_log=None):
        super().__init__(parent, bg=Theme.BG)
        self.media_type = media_type
        self.get_drive = get_drive_callback
        self.on_log = on_log or (lambda msg: None)

        self.view_mode = "grid"  # 'grid' or 'list'
        self.sort_key = "name_asc"
        self.search_filter = ""
        self.selected_file = None
        self.files_data = []
        self.current_display_files = []
        self.photo_refs = []

        self.active_subtab = "files"  # 'files' or 'playlists' (audio only)
        self.current_pl_name = None

        self._build_ui()

    def _get_folder(self):
        drive = self.get_drive()
        if not drive:
            return None
        return get_music_dir(drive) if self.media_type == "audio" else get_video_dir(drive)

    def _get_exts(self):
        return AUDIO_EXTS if self.media_type == "audio" else VIDEO_EXTS

    def _build_ui(self):
        # ── Header / Sub-tabs ──
        self.top_bar = tk.Frame(self, bg=Theme.BG)
        self.top_bar.pack(fill="x", pady=(0, 6))

        files_label = "Music Files" if self.media_type == "audio" else "Video Files"
        files_icon = "music_note" if self.media_type == "audio" else "movie"

        self.tab_files_btn = create_flat_btn(
            self.top_bar, files_label, icon_name=files_icon, bg=Theme.ACCENT, fg="#ffffff",
            command=lambda: self.switch_subtab("files"), font=("Segoe UI", 9, "bold")
        )
        self.tab_files_btn.pack(side="left", padx=(0, 4))

        self.tab_pl_btn = create_flat_btn(
            self.top_bar, "Playlists", icon_name="queue_music", bg=Theme.SURFACE2, fg=Theme.TEXT_DIM,
            command=lambda: self.switch_subtab("playlists"), font=("Segoe UI", 9, "bold")
        )
        self.tab_pl_btn.pack(side="left")

        # ── Sub-tab Container ──
        self.subtab_container = tk.Frame(self, bg=Theme.BG)
        self.subtab_container.pack(fill="both", expand=True)

        # 1. Files Frame
        self.files_frame = tk.Frame(self.subtab_container, bg=Theme.BG)
        self._build_files_ui(self.files_frame)

        # 2. Playlists Frame (both audio and video)
        self.pl_frame = tk.Frame(self.subtab_container, bg=Theme.BG)
        self._build_playlists_ui(self.pl_frame)

        self.switch_subtab("files")

    def switch_subtab(self, subtab):
        self.active_subtab = subtab
        if subtab == "files":
            self.tab_files_btn.config(bg=Theme.ACCENT, fg="#ffffff")
            self.tab_pl_btn.config(bg=Theme.SURFACE2, fg=Theme.TEXT_DIM)
            if hasattr(self, 'pl_frame'):
                self.pl_frame.pack_forget()
            self.files_frame.pack(fill="both", expand=True)
            self.refresh()
        else:
            self.tab_files_btn.config(bg=Theme.SURFACE2, fg=Theme.TEXT_DIM)
            self.tab_pl_btn.config(bg=Theme.ACCENT, fg="#ffffff")
            self.files_frame.pack_forget()
            self.pl_frame.pack(fill="both", expand=True)
            self.refresh_playlists()

    # ─── FILES MANAGEMENT VIEW ────────────────────────────────────────────────

    def _build_files_ui(self, parent):
        ctrl_bar = tk.Frame(parent, bg=Theme.BG)
        ctrl_bar.pack(fill="x", pady=(0, 6))

        # Search / Filter
        search_f = tk.Frame(ctrl_bar, bg=Theme.SURFACE2, highlightbackground=Theme.BORDER, highlightthickness=1)
        search_f.pack(side="left", fill="x", expand=True, padx=(0, 6))

        s_icon = get_icon_photo("search", size=14, color=Theme.TEXT_DIM)
        s_lbl = tk.Label(search_f, image=s_icon, bg=Theme.SURFACE2, padx=6)
        s_lbl.image = s_icon
        s_lbl.pack(side="left")

        self.filter_var = tk.StringVar()
        self.filter_entry = tk.Entry(
            search_f, textvariable=self.filter_var, fg=Theme.TEXT, font=FONT_BODY,
            borderwidth=0, relief="flat", bg=Theme.SURFACE2, insertbackground=Theme.TEXT
        )
        self.filter_entry.pack(side="left", fill="both", expand=True, ipady=4)
        self.filter_entry.bind("<KeyRelease>", lambda e: self._on_filter_changed())

        # Sort Dropdown
        sort_opts = [
            ("Name (A-Z)", "name_asc"),
            ("Name (Z-A)", "name_desc"),
            ("Date (Newest)", "date_desc"),
            ("Date (Oldest)", "date_asc"),
            ("Size (Largest)", "size_desc"),
            ("Size (Smallest)", "size_asc"),
        ]
        self._sort_map = dict(sort_opts)
        self._sort_label_map = {v: k for k, v in sort_opts}

        self.sort_combo = ttk.Combobox(ctrl_bar, state="readonly", style="App.TCombobox", width=14, font=FONT_SMALL)
        self.sort_combo['values'] = [k for k, _ in sort_opts]
        self.sort_combo.current(0)
        self.sort_combo.pack(side="left", padx=(0, 6))
        self.sort_combo.bind("<<ComboboxSelected>>", self._on_sort_changed)

        # Grid / List View Toggle (with Google Material vector icons)
        self.view_grid_btn = create_flat_btn(ctrl_bar, "Grid", icon_name="grid_view", bg=Theme.ACCENT, fg="#ffffff",
                                             command=lambda: self.set_view_mode("grid"), font=("Segoe UI", 8, "bold"))
        self.view_grid_btn.pack(side="left", padx=(0, 2))

        self.view_list_btn = create_flat_btn(ctrl_bar, "List", icon_name="view_list", bg=Theme.SURFACE2, fg=Theme.TEXT_DIM,
                                             command=lambda: self.set_view_mode("list"), font=("Segoe UI", 8, "bold"))
        self.view_list_btn.pack(side="left")

        # View Area (Container for Grid / List)
        self.view_container = tk.Frame(parent, bg=Theme.BORDER, padx=1, pady=1)
        self.view_container.pack(fill="both", expand=True, pady=(0, 6))

        # 1. Grid View (Canvas with scrollbar)
        self.grid_canvas = tk.Canvas(self.view_container, bg=Theme.SURFACE, highlightthickness=0)
        self.grid_scrollbar = ttk.Scrollbar(self.view_container, orient="vertical", command=self.grid_canvas.yview)
        self.grid_content = tk.Frame(self.grid_canvas, bg=Theme.SURFACE)

        self._grid_win = self.grid_canvas.create_window((0, 0), window=self.grid_content, anchor="nw")
        self.grid_canvas.bind("<Configure>", lambda e: self.grid_canvas.itemconfig(self._grid_win, width=e.width))
        self.grid_canvas.configure(yscrollcommand=self.grid_scrollbar.set)
        self._bind_mousewheel(self.grid_canvas, self.grid_content)

        # 2. List View (Treeview with scrollbar)
        cols = ("name", "size", "date")
        self.tree = ttk.Treeview(self.view_container, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("name", text="File Name")
        self.tree.heading("size", text="Size")
        self.tree.heading("date", text="Date Modified")
        self.tree.column("name", width=220, anchor="w")
        self.tree.column("size", width=70, anchor="e")
        self.tree.column("date", width=120, anchor="center")

        style = ttk.Style()
        style.configure("Panel.Treeview", background=Theme.SURFACE, fieldbackground=Theme.SURFACE,
                        foreground=Theme.TEXT, rowheight=26, borderwidth=0)
        style.configure("Panel.Treeview.Heading", background=Theme.SURFACE2, foreground=Theme.TEXT, borderwidth=0)
        style.map("Panel.Treeview", background=[("selected", Theme.ACCENT)], foreground=[("selected", "#ffffff")])
        self.tree.configure(style="Panel.Treeview")

        self.list_scrollbar = ttk.Scrollbar(self.view_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.list_scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-Button-1>", lambda e: self.edit_thumbnail())
        self.tree.bind("<Button-3>", self._show_tree_context_menu)

        # Bottom Action Bar with Google Material Icons
        action_bar = tk.Frame(parent, bg=Theme.BG)
        action_bar.pack(fill="x")

        create_flat_btn(action_bar, "Thumbnail", icon_name="image", bg=Theme.SURFACE2, fg=Theme.ACCENT, hover_bg=Theme.BORDER,
                        command=self.edit_thumbnail, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        create_flat_btn(action_bar, "Rename", icon_name="edit", bg=Theme.ACCENT, fg="#ffffff", hover_bg=Theme.ACCENT2,
                        command=self.rename_selected, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        create_flat_btn(action_bar, "Delete", icon_name="delete", bg=Theme.ERROR, fg="#ffffff", hover_bg=Theme.BORDER,
                        command=self.delete_selected, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        create_flat_btn(action_bar, "Open Folder", icon_name="folder", bg=Theme.SURFACE2, fg=Theme.TEXT, hover_bg=Theme.BORDER,
                        command=self.open_folder, font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        create_flat_btn(action_bar, "Refresh", icon_name="sync", bg=Theme.SURFACE2, fg=Theme.TEXT, hover_bg=Theme.BORDER,
                        command=self.refresh, font=("Segoe UI", 9)).pack(side="left")

        # Hover info status strip
        self.hover_info_lbl = tk.Label(
            parent, text="Hover over a file to see its full name · Double-click to edit thumbnail",
            font=("Segoe UI", 8), fg=Theme.TEXT_DIM, bg=Theme.BG, anchor="w"
        )
        self.hover_info_lbl.pack(fill="x", pady=(4, 0))

        # Two-finger and mousewheel scrolling on list view tree
        def _scroll_tree(event):
            if event.num == 4:
                self.tree.yview_scroll(-2, "units")
            elif event.num == 5:
                self.tree.yview_scroll(2, "units")
            elif event.delta:
                units = -1 if event.delta > 0 else 1
                self.tree.yview_scroll(units, "units")
        self.tree.bind("<Button-4>", _scroll_tree, add="+")
        self.tree.bind("<Button-5>", _scroll_tree, add="+")
        self.tree.bind("<MouseWheel>", _scroll_tree, add="+")
        self.tree.bind("<Motion>", self._on_tree_motion, add="+")

        self.set_view_mode(self.view_mode)

    def _bind_mousewheel(self, canvas, frame):
        def _scroll(event):
            if event.num == 4:
                canvas.yview_scroll(-2, "units")
            elif event.num == 5:
                canvas.yview_scroll(2, "units")
            elif event.delta:
                units = -1 if event.delta > 0 else 1
                if abs(event.delta) >= 60:
                    units = -1 * int(event.delta / 60)
                canvas.yview_scroll(units, "units")

        self._grid_scroll_fn = _scroll
        canvas.bind("<MouseWheel>", _scroll)
        canvas.bind("<Button-4>", _scroll)
        canvas.bind("<Button-5>", _scroll)
        frame.bind("<MouseWheel>", _scroll)
        frame.bind("<Button-4>", _scroll)
        frame.bind("<Button-5>", _scroll)

    def _bind_scroll_recursive(self, widget):
        if hasattr(self, '_grid_scroll_fn'):
            widget.bind("<MouseWheel>", self._grid_scroll_fn, add="+")
            widget.bind("<Button-4>", self._grid_scroll_fn, add="+")
            widget.bind("<Button-5>", self._grid_scroll_fn, add="+")
        for child in widget.winfo_children():
            self._bind_scroll_recursive(child)

    def set_view_mode(self, mode):
        self.view_mode = mode
        if mode == "grid":
            self.view_grid_btn.config(bg=Theme.ACCENT, fg="#ffffff")
            self.view_list_btn.config(bg=Theme.SURFACE2, fg=Theme.TEXT_DIM)
            self.tree.pack_forget()
            self.list_scrollbar.pack_forget()
            self.grid_canvas.pack(side="left", fill="both", expand=True)
            self.grid_scrollbar.pack(side="right", fill="y")
            self._render_grid_view()
        else:
            self.view_grid_btn.config(bg=Theme.SURFACE2, fg=Theme.TEXT_DIM)
            self.view_list_btn.config(bg=Theme.ACCENT, fg="#ffffff")
            self.grid_canvas.pack_forget()
            self.grid_scrollbar.pack_forget()
            self.tree.pack(side="left", fill="both", expand=True)
            self.list_scrollbar.pack(side="right", fill="y")
            self._render_list_view()

    def refresh(self):
        folder = self._get_folder()
        if not folder or not os.path.exists(folder):
            self.files_data = []
        else:
            self.files_data = get_detailed_media_files(folder, self._get_exts())
        self._apply_filter_and_render()

    def _on_filter_changed(self):
        self.search_filter = self.filter_var.get().strip().lower()
        self._apply_filter_and_render()

    def _on_sort_changed(self, event=None):
        label = self.sort_combo.get()
        self.sort_key = self._sort_map.get(label, "name_asc")
        self._apply_filter_and_render()

    def _apply_filter_and_render(self):
        filtered = self.files_data
        if self.search_filter:
            filtered = [f for f in filtered if self.search_filter in f['name'].lower()]
        self.current_display_files = sort_media_files(filtered, self.sort_key)

        if self.view_mode == "grid":
            self._render_grid_view()
        else:
            self._render_list_view()

    def _render_list_view(self):
        HoverTooltip.close_active()
        self.tree.delete(*self.tree.get_children())
        for f in self.current_display_files:
            self.tree.insert("", tk.END, iid=f['name'], values=(f['name'], f['size_str'], f['date_str']))
        if self.selected_file and self.tree.exists(self.selected_file):
            self.tree.selection_set(self.selected_file)

    def _on_tree_select(self, event=None):
        sel = self.tree.selection()
        if sel:
            self.selected_file = sel[0]
            if hasattr(self, 'hover_info_lbl'):
                self.hover_info_lbl.config(text=sel[0], fg=Theme.TEXT)

    def _on_tree_motion(self, event):
        iid = self.tree.identify_row(event.y)
        if iid and hasattr(self, 'hover_info_lbl'):
            self.hover_info_lbl.config(text=iid, fg=Theme.TEXT)

    def _render_grid_view(self):
        HoverTooltip.close_active()
        for w in self.grid_content.winfo_children():
            w.destroy()
        self.photo_refs = []

        if not self.current_display_files:
            empty_lbl = tk.Label(
                self.grid_content, text="No media files found.",
                font=("Segoe UI", 10), fg=Theme.TEXT_DIM, bg=Theme.SURFACE, pady=30
            )
            empty_lbl.pack(fill="both", expand=True)
            self.grid_canvas.configure(scrollregion=self.grid_canvas.bbox("all"))
            return

        columns = 2
        card_w = 200
        card_h = 168

        self.grid_content.columnconfigure(0, weight=1)
        self.grid_content.columnconfigure(1, weight=1)

        for idx, f_info in enumerate(self.current_display_files):
            r = idx // columns
            c = idx % columns

            card = tk.Frame(self.grid_content, bg=Theme.SURFACE2, highlightbackground=Theme.BORDER,
                            highlightthickness=1, width=card_w, height=card_h, cursor="hand2")
            card.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")
            card.pack_propagate(False)

            is_sel = (self.selected_file == f_info['name'])
            if is_sel:
                card.config(highlightbackground=Theme.ACCENT, highlightthickness=2)

            thumb_box = tk.Frame(card, bg=Theme.SURFACE, width=card_w - 16, height=100)
            thumb_box.pack(padx=8, pady=(8, 4))
            thumb_box.pack_propagate(False)

            thumb_lbl = tk.Label(thumb_box, bg=Theme.SURFACE)
            thumb_lbl.pack(fill="both", expand=True)

            target_sz = (card_w - 16, 100) if self.media_type == "video" else (100, 100)
            cover_img = get_cached_cover(f_info['path'], self.media_type, target_size=target_sz)
            if cover_img:
                photo = ImageTk.PhotoImage(cover_img)
                self.photo_refs.append(photo)
                thumb_lbl.config(image=photo)
                thumb_lbl.image = photo
            else:
                ic_name = "music_note" if self.media_type == "audio" else "movie"
                ph = get_icon_photo(ic_name, size=32, color=Theme.TEXT_DIM)
                thumb_lbl.config(image=ph)
                thumb_lbl.image = ph

            lbl_title = tk.Label(card, text=f_info['name'], font=("Segoe UI", 9, "bold"),
                                 fg=Theme.TEXT, bg=Theme.SURFACE2, anchor="w")
            lbl_title.pack(fill="x", padx=8)

            lbl_meta = tk.Label(card, text=f"{f_info['size_str']}  ·  {f_info['date_str'][:10]}",
                                font=("Segoe UI", 8), fg=Theme.TEXT_DIM, bg=Theme.SURFACE2, anchor="w")
            lbl_meta.pack(fill="x", padx=8, pady=(0, 4))

            interactive_widgets = [card, thumb_box, thumb_lbl, lbl_title, lbl_meta]
            for w in interactive_widgets:
                w.bind("<Button-1>", lambda e, fname=f_info['name']: self._select_card(fname))
                w.bind("<Double-Button-1>", lambda e, fname=f_info['name']: self.edit_thumbnail(fname))
                w.bind("<Button-3>", lambda e, fname=f_info['name']: self._show_context_menu(e, fname))
                w.bind("<Enter>", lambda e, c=card, info=f_info: self._on_card_enter(c, info), add="+")
                w.bind("<Leave>", lambda e, c=card: self._on_card_leave(c), add="+")
                HoverTooltip(w, f_info['name'], f_info['size_str'], f_info['date_str'], self.media_type)

            self._bind_scroll_recursive(card)

        self.grid_content.update_idletasks()
        self.grid_canvas.configure(scrollregion=self.grid_canvas.bbox("all"))

    def _on_card_enter(self, card, info):
        card.config(bg=Theme.BORDER)
        if hasattr(self, 'hover_info_lbl'):
            self.hover_info_lbl.config(
                text=f"{info['name']}   ({info['size_str']} · {info['date_str'][:10]})",
                fg=Theme.TEXT
            )

    def _on_card_leave(self, card):
        card.config(bg=Theme.SURFACE2)
        if hasattr(self, 'hover_info_lbl'):
            self.hover_info_lbl.config(
                text="Hover over a file to see its full name · Double-click to edit thumbnail",
                fg=Theme.TEXT_DIM
            )

    def _select_card(self, fname):
        self.selected_file = fname
        self._render_grid_view()

    def edit_thumbnail(self, fname=None):
        target = fname or self.selected_file
        if not target:
            messagebox.showinfo("Select File", "Please select a media file to update its thumbnail.", parent=self)
            return

        folder = self._get_folder()
        if not folder:
            messagebox.showwarning("No Drive", "Please connect your PSP first.", parent=self)
            return

        filepath = os.path.join(folder, target)
        if not os.path.exists(filepath):
            messagebox.showerror("Error", f"File not found: " + filepath, parent=self)
            return

        def _on_cover_updated():
            self.refresh()
            self.on_log(f"Updated thumbnail for: {target}")

        ThumbnailEditorDialog(self, filepath, self.media_type, on_applied=_on_cover_updated)

    def _show_context_menu(self, event, fname):
        self._select_card(fname)
        menu = tk.Menu(self, tearoff=0, bg=Theme.SURFACE, fg=Theme.TEXT, activebackground=Theme.ACCENT, activeforeground="#ffffff")
        menu.add_command(label="Change Thumbnail…", command=lambda: self.edit_thumbnail(fname))
        menu.add_command(label="Rename…", command=self.rename_selected)
        menu.add_separator()
        menu.add_command(label="Delete", command=self.delete_selected)
        menu.add_command(label="Open in File Explorer", command=self.open_folder)
        menu.tk_popup(event.x_root, event.y_root)

    def _show_tree_context_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.selected_file = iid
            self._show_context_menu(event, iid)

    def rename_selected(self):
        target = self.selected_file
        if not target:
            messagebox.showinfo("Select File", "Please select a file to rename first.")
            return

        folder = self._get_folder()
        drive = self.get_drive()
        old_base = os.path.splitext(target)[0]
        new_base = simpledialog.askstring("Rename", f"New name for:\n{target}", initialvalue=old_base, parent=self)
        if not new_base:
            return

        try:
            new_name = rename_media_file(folder, drive, self.media_type, target, new_base)
            self.selected_file = new_name
            self.refresh()
            self.on_log(f"Renamed: {target} → {new_name}")
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def delete_selected(self):
        target = self.selected_file
        if not target:
            messagebox.showinfo("Select File", "Please select a file to delete first.")
            return

        if not messagebox.askyesno("Confirm Delete", f"Delete '{target}' from PSP storage?", parent=self):
            return

        folder = self._get_folder()
        try:
            delete_media_files(folder, self.media_type, [target])
            self.on_log(f"Deleted from PSP: {target}")
            self.selected_file = None
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def open_folder(self):
        folder = self._get_folder()
        if folder and os.path.exists(folder):
            open_system_folder(folder)
        else:
            messagebox.showwarning("No Folder", "Connect PSP and ensure media folders exist.")

    # ─── IN-PANE PLAYLISTS MANAGEMENT VIEW ────────────────────────────────────

    def _build_playlists_ui(self, parent):
        top_row = tk.Frame(parent, bg=Theme.BG)
        top_row.pack(fill="x", pady=(0, 6))

        tk.Label(top_row, text="Playlist:", font=("Segoe UI", 9, "bold"), fg=Theme.TEXT, bg=Theme.BG).pack(side="left", padx=(0, 6))

        self.pl_combo = ttk.Combobox(top_row, state="readonly", style="App.TCombobox", width=18, font=FONT_BODY)
        self.pl_combo.pack(side="left", padx=(0, 6))
        self.pl_combo.bind("<<ComboboxSelected>>", self._on_pl_combo_selected)

        create_flat_btn(top_row, "New", icon_name="add", bg=Theme.ACCENT, fg="#ffffff", hover_bg=Theme.ACCENT2,
                        command=self.new_playlist, font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 3))
        create_flat_btn(top_row, "Rename", icon_name="edit", bg=Theme.SURFACE2, fg=Theme.TEXT, hover_bg=Theme.BORDER,
                        command=self.rename_playlist_ui, font=("Segoe UI", 8)).pack(side="left", padx=(0, 3))
        create_flat_btn(top_row, "Delete", icon_name="delete", bg=Theme.ERROR, fg="#ffffff", hover_bg=Theme.BORDER,
                        command=self.delete_playlist_ui, font=("Segoe UI", 8)).pack(side="left")

        # Status / Title Banner
        self.pl_info_var = tk.StringVar(value="Select or create a playlist above")
        tk.Label(parent, textvariable=self.pl_info_var, font=("Segoe UI", 9, "bold"),
                 fg=Theme.ACCENT, bg=Theme.BG, anchor="w").pack(fill="x", pady=(2, 4))

        # Tracks Treeview Container
        tree_outer = tk.Frame(parent, bg=Theme.BORDER, padx=1, pady=1)
        tree_outer.pack(fill="both", expand=True, pady=(0, 6))

        cols = ("idx", "name")
        self.pl_tree = ttk.Treeview(tree_outer, columns=cols, show="headings", selectmode="extended")
        self.pl_tree.heading("idx", text="#")
        col_title = "Track Name" if self.media_type == "audio" else "Video Title"
        self.pl_tree.heading("name", text=col_title)
        self.pl_tree.column("idx", width=40, anchor="center")
        self.pl_tree.column("name", width=360, anchor="w")

        style = ttk.Style()
        style.configure("PL.Treeview", background=Theme.SURFACE, fieldbackground=Theme.SURFACE,
                        foreground=Theme.TEXT, rowheight=24, borderwidth=0)
        style.map("PL.Treeview", background=[("selected", Theme.ACCENT)], foreground=[("selected", "#ffffff")])
        self.pl_tree.configure(style="PL.Treeview")

        pl_sb = ttk.Scrollbar(tree_outer, orient="vertical", command=self.pl_tree.yview)
        self.pl_tree.configure(yscrollcommand=pl_sb.set)
        self.pl_tree.pack(side="left", fill="both", expand=True)
        pl_sb.pack(side="right", fill="y")

        # Bottom Playlist Controls (Google Material icons)
        pl_bottom = tk.Frame(parent, bg=Theme.BG)
        pl_bottom.pack(fill="x")

        add_btn_txt = "Add Songs" if self.media_type == "audio" else "Add Videos"
        create_flat_btn(pl_bottom, add_btn_txt, icon_name="add", bg=Theme.ACCENT, fg="#ffffff", hover_bg=Theme.ACCENT2,
                        command=self.add_media_to_playlist, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        create_flat_btn(pl_bottom, "Remove", icon_name="delete", bg=Theme.ERROR, fg="#ffffff", hover_bg=Theme.BORDER,
                        command=self.remove_selected_tracks, font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        create_flat_btn(pl_bottom, "Move Up", icon_name="arrow_up", bg=Theme.SURFACE2, fg=Theme.TEXT, hover_bg=Theme.BORDER,
                        command=self.move_track_up, font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        create_flat_btn(pl_bottom, "Move Down", icon_name="arrow_down", bg=Theme.SURFACE2, fg=Theme.TEXT, hover_bg=Theme.BORDER,
                        command=self.move_track_down, font=("Segoe UI", 9)).pack(side="left")

    def _get_pl_dir(self):
        drive = self.get_drive()
        return get_playlist_dir(drive, self.media_type) if drive else None

    def refresh_playlists(self):
        pl_dir = self._get_pl_dir()
        if not pl_dir or not os.path.exists(pl_dir):
            self.pl_combo['values'] = []
            self.pl_combo.set("")
            self.pl_tree.delete(*self.pl_tree.get_children())
            self.pl_info_var.set("Connect PSP to manage playlists")
            return

        playlists = list_playlists(pl_dir)
        self.pl_combo['values'] = playlists
        if playlists:
            if not self.current_pl_name or self.current_pl_name not in playlists:
                self.current_pl_name = playlists[0]
            self.pl_combo.set(self.current_pl_name)
            self._load_current_playlist_tracks()
        else:
            self.current_pl_name = None
            self.pl_combo.set("")
            self.pl_tree.delete(*self.pl_tree.get_children())
            self.pl_info_var.set("No playlists found. Click 'New' to create one.")

    def _on_pl_combo_selected(self, event=None):
        self.current_pl_name = self.pl_combo.get()
        self._load_current_playlist_tracks()

    def _load_current_playlist_tracks(self):
        self.pl_tree.delete(*self.pl_tree.get_children())
        if not self.current_pl_name:
            return

        pl_dir = self._get_pl_dir()
        lines = read_playlist(pl_dir, self.current_pl_name)
        for idx, line in enumerate(lines):
            disp = song_display_name(line)
            self.pl_tree.insert("", tk.END, iid=str(idx), values=(str(idx + 1), disp))

        unit = "songs" if self.media_type == "audio" else "videos"
        self.pl_info_var.set(f"Playlist: '{self.current_pl_name}' ({len(lines)} {unit})")

    def new_playlist(self):
        drive = self.get_drive()
        if not drive:
            messagebox.showwarning("No Drive", "Connect your PSP first.")
            return

        name = simpledialog.askstring("New Playlist", "Playlist name:", parent=self)
        if not name:
            return
        name = name.strip()
        pl_dir = self._get_pl_dir()
        ok, err = create_playlist(pl_dir, name)
        if not ok:
            messagebox.showwarning("Exists", f"'{name}' already exists.", parent=self)
            return

        self.current_pl_name = name
        self.refresh_playlists()
        self.on_log(f"Created playlist: {name}")

    def rename_playlist_ui(self):
        if not self.current_pl_name:
            return
        old = self.current_pl_name
        new = simpledialog.askstring("Rename", "New name for playlist:", initialvalue=old, parent=self)
        if not new or new.strip() == old:
            return
        new = new.strip()
        pl_dir = self._get_pl_dir()
        try:
            rename_playlist(pl_dir, old, new)
            self.current_pl_name = new
            self.refresh_playlists()
            self.on_log(f"Renamed playlist: {old} → {new}")
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def delete_playlist_ui(self):
        if not self.current_pl_name:
            return
        if not messagebox.askyesno("Delete", f"Delete playlist '{self.current_pl_name}' from PSP?", parent=self):
            return
        pl_dir = self._get_pl_dir()
        try:
            delete_playlist(pl_dir, self.current_pl_name)
            self.on_log(f"Deleted playlist: {self.current_pl_name}")
            self.current_pl_name = None
            self.refresh_playlists()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def add_media_to_playlist(self):
        if not self.current_pl_name:
            messagebox.showinfo("Select Playlist", "Please select or create a playlist first.", parent=self)
            return

        drive = self.get_drive()
        if not drive:
            messagebox.showwarning("No Drive", "Connect your PSP first.", parent=self)
            return

        folder = get_music_dir(drive) if self.media_type == "audio" else get_video_dir(drive)
        avail = list_available_media(folder, self.media_type)
        item_label = "songs" if self.media_type == "audio" else "videos"
        folder_label = "MUSIC" if self.media_type == "audio" else "VIDEO"

        if not avail:
            messagebox.showinfo(f"No {item_label.capitalize()}", f"No media files found in PSP {folder_label} folder.", parent=self)
            return

        pick = tk.Toplevel(self)
        pick.title(f"Add {item_label.capitalize()} to Playlist")
        pick.geometry("500x440")
        pick.configure(bg=Theme.BG)
        pick.transient(self)
        pick.wait_visibility()
        pick.grab_set()

        tk.Label(pick, text=f"Add {item_label} to '{self.current_pl_name}':",
                 font=("Segoe UI", 10, "bold"), fg=Theme.TEXT, bg=Theme.BG).pack(padx=16, pady=(12, 4), anchor="w")

        pick_search_f = tk.Frame(pick, bg=Theme.SURFACE2, highlightbackground=Theme.BORDER, highlightthickness=1)
        pick_search_f.pack(fill="x", padx=16, pady=(0, 6))

        s_icon = get_icon_photo("search", size=14, color=Theme.TEXT_DIM)
        s_lbl = tk.Label(pick_search_f, image=s_icon, bg=Theme.SURFACE2, padx=6)
        s_lbl.image = s_icon
        s_lbl.pack(side="left")

        pick_filter_var = tk.StringVar()
        pick_entry = tk.Entry(pick_search_f, textvariable=pick_filter_var, fg=Theme.TEXT, font=FONT_BODY,
                              borderwidth=0, relief="flat", bg=Theme.SURFACE2, insertbackground=Theme.TEXT)
        pick_entry.pack(side="left", fill="both", expand=True, ipady=4)

        pick_outer = tk.Frame(pick, bg=Theme.BORDER, padx=1, pady=1)
        pick_outer.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        pick_lb = tk.Listbox(pick_outer, bg=Theme.SURFACE, fg=Theme.TEXT, font=("Segoe UI", 10),
                             selectbackground=Theme.ACCENT, selectforeground="#ffffff",
                             borderwidth=0, highlightthickness=0, selectmode="extended")
        pick_sb = ttk.Scrollbar(pick_outer, orient="vertical", command=pick_lb.yview)
        pick_lb.configure(yscrollcommand=pick_sb.set)
        pick_lb.pack(side="left", fill="both", expand=True)
        pick_sb.pack(side="right", fill="y")

        pl_dir = self._get_pl_dir()
        existing = read_playlist(pl_dir, self.current_pl_name)
        existing_set = {song_display_name(l).lower() for l in existing}

        candidate_media = [f for f in avail if f.lower() not in existing_set]

        def _update_picker_list(*args):
            q = pick_filter_var.get().strip().lower()
            pick_lb.delete(0, tk.END)
            for f in candidate_media:
                if not q or q in f.lower():
                    pick_lb.insert(tk.END, f)

        pick_filter_var.trace("w", _update_picker_list)
        _update_picker_list()

        def confirm_add():
            sel_indices = pick_lb.curselection()
            if not sel_indices:
                pick.destroy()
                return
            lines = read_playlist(pl_dir, self.current_pl_name)
            added_count = 0
            prefix = "\\MUSIC\\" if self.media_type == "audio" else "\\VIDEO\\"
            for idx in sel_indices:
                fname = pick_lb.get(idx)
                lines.append(f"{prefix}{fname}")
                added_count += 1
            write_playlist(pl_dir, self.current_pl_name, lines)
            self._load_current_playlist_tracks()
            self.on_log(f"Added {added_count} {item_label} to playlist '{self.current_pl_name}'")
            pick.destroy()

        def select_all():
            pick_lb.select_set(0, tk.END)

        add_row = tk.Frame(pick, bg=Theme.BG)
        add_row.pack(fill="x", padx=16, pady=(0, 12))
        create_flat_btn(add_row, "Add Selected", icon_name="add", bg=Theme.ACCENT, fg="#ffffff", hover_bg=Theme.ACCENT2,
                        command=confirm_add, font=("Segoe UI", 9, "bold")).pack(side="left")
        create_flat_btn(add_row, "Select All", bg=Theme.SURFACE2, fg=Theme.TEXT, hover_bg=Theme.BORDER,
                        command=select_all, font=("Segoe UI", 9)).pack(side="left", padx=(6, 0))
        create_flat_btn(add_row, "Cancel", bg=Theme.SURFACE2, fg=Theme.TEXT, hover_bg=Theme.BORDER,
                        command=pick.destroy, font=("Segoe UI", 9)).pack(side="left", padx=(6, 0))

    add_songs_to_playlist = add_media_to_playlist

    def remove_selected_tracks(self):
        sel = self.pl_tree.selection()
        if not sel or not self.current_pl_name:
            return

        pl_dir = self._get_pl_dir()
        lines = read_playlist(pl_dir, self.current_pl_name)
        remove_indices = {int(iid) for iid in sel}
        new_lines = [line for i, line in enumerate(lines) if i not in remove_indices]

        write_playlist(pl_dir, self.current_pl_name, new_lines)
        self._load_current_playlist_tracks()
        self.on_log(f"Removed {len(remove_indices)} track(s) from '{self.current_pl_name}'")

    def move_track_up(self):
        sel = self.pl_tree.selection()
        if not sel or not self.current_pl_name:
            return
        idx = int(sel[0])
        if idx <= 0:
            return

        pl_dir = self._get_pl_dir()
        lines = read_playlist(pl_dir, self.current_pl_name)
        lines[idx - 1], lines[idx] = lines[idx], lines[idx - 1]
        write_playlist(pl_dir, self.current_pl_name, lines)
        self._load_current_playlist_tracks()
        self.pl_tree.selection_set(str(idx - 1))

    def move_track_down(self):
        sel = self.pl_tree.selection()
        if not sel or not self.current_pl_name:
            return
        idx = int(sel[-1])

        pl_dir = self._get_pl_dir()
        lines = read_playlist(pl_dir, self.current_pl_name)
        if idx >= len(lines) - 1:
            return
        lines[idx], lines[idx + 1] = lines[idx + 1], lines[idx]
        write_playlist(pl_dir, self.current_pl_name, lines)
        self._load_current_playlist_tracks()
        self.pl_tree.selection_set(str(idx + 1))
