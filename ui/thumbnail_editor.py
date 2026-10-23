import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

from ui.theme import Theme, FONT_BODY, FONT_SMALL
from ui.components import create_flat_btn
from core.media_manager import get_file_cover, update_media_cover

class ThumbnailEditorDialog(tk.Toplevel):
    """
    Interactive image cropper, zoomer, and pan editor for PSP media thumbnails.
    - Music: Target 1:1 square ratio (600x600 embedded ID3 APIC cover).
    - Video: Target 4:3 ratio (160x120 companion .thm thumbnail).
    """

    def __init__(self, parent, filepath, media_type, on_applied=None):
        super().__init__(parent)
        self.filepath = filepath
        self.media_type = media_type
        self.on_applied = on_applied or (lambda: None)

        self.filename = os.path.basename(filepath)
        self.title(f"Thumbnail Editor — {self.filename}")
        self.geometry("560x590")
        self.configure(bg=Theme.BG)
        self.resizable(False, False)
        self.transient(parent)

        # Canvas & Crop Box Dimensions
        self.canvas_w = 520
        self.canvas_h = 360

        if media_type == "audio":
            self.crop_w = 260
            self.crop_h = 260
            self.target_ratio_str = "1:1 Square (600×600 MP3 Album Art)"
        else:
            self.crop_w = 320
            self.crop_h = 240
            self.target_ratio_str = "4:3 Ratio (160×120 PSP Video .THM)"

        self.cx0 = (self.canvas_w - self.crop_w) // 2
        self.cy0 = (self.canvas_h - self.crop_h) // 2
        self.cx1 = self.cx0 + self.crop_w
        self.cy1 = self.cy0 + self.crop_h

        # Transformation State
        self.orig_image = None
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self._disp_photo = None

        self._build_ui()
        self._load_initial_image()

        self.wait_visibility()
        self.grab_set()

    def _build_ui(self):
        tk.Frame(self, bg=Theme.ACCENT, height=3).pack(fill="x")

        # Header Info
        hdr = tk.Frame(self, bg=Theme.BG)
        hdr.pack(fill="x", padx=16, pady=(10, 4))

        icon_name = "music_note" if self.media_type == "audio" else "movie"
        tk.Label(hdr, text=self.filename, font=("Segoe UI", 11, "bold"),
                 fg=Theme.TEXT, bg=Theme.BG, anchor="w").pack(fill="x")

        tk.Label(hdr, text=f"Target: {self.target_ratio_str}  ·  Drag to pan, scroll wheel or slider to zoom",
                 font=FONT_SMALL, fg=Theme.TEXT_DIM, bg=Theme.BG, anchor="w").pack(fill="x", pady=(2, 0))

        # Main Interactive Canvas Outer Frame
        canvas_outer = tk.Frame(self, bg=Theme.BORDER, padx=1, pady=1)
        canvas_outer.pack(padx=16, pady=(6, 8))

        self.canvas = tk.Canvas(canvas_outer, bg="#0a0a0a", width=self.canvas_w, height=self.canvas_h,
                                highlightthickness=0, cursor="fleur")
        self.canvas.pack()

        # Canvas Mouse Bindings for Panning and Zooming
        self.canvas.bind("<ButtonPress-1>", self._on_pan_start)
        self.canvas.bind("<B1-Motion>", self._on_pan_drag)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", lambda e: self._zoom_step(1.1))
        self.canvas.bind("<Button-5>", lambda e: self._zoom_step(0.9))

        # Zoom Controls Bar
        zoom_bar = tk.Frame(self, bg=Theme.BG)
        zoom_bar.pack(fill="x", padx=16, pady=(0, 10))

        tk.Label(zoom_bar, text="Zoom:", font=("Segoe UI", 9, "bold"), fg=Theme.TEXT, bg=Theme.BG).pack(side="left", padx=(0, 8))

        self.zoom_var = tk.DoubleVar(value=100)
        self.zoom_scale = tk.Scale(
            zoom_bar, from_=30, to=400, orient="horizontal", variable=self.zoom_var,
            bg=Theme.BG, fg=Theme.TEXT, highlightthickness=0, troughcolor=Theme.SURFACE2,
            activebackground=Theme.ACCENT, command=self._on_slider_zoom, showvalue=False, length=240
        )
        self.zoom_scale.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.zoom_val_lbl = tk.Label(zoom_bar, text="100%", font=FONT_SMALL, fg=Theme.TEXT_DIM, bg=Theme.BG, width=6)
        self.zoom_val_lbl.pack(side="left", padx=(0, 8))

        create_flat_btn(zoom_bar, "Reset Fit", icon_name="refresh", bg=Theme.SURFACE2, fg=Theme.TEXT, hover_bg=Theme.BORDER,
                        command=self.fit_to_crop_frame, font=("Segoe UI", 8)).pack(side="left")

        # Bottom Action Bar
        btn_bar = tk.Frame(self, bg=Theme.BG)
        btn_bar.pack(fill="x", padx=16, pady=(0, 12))

        create_flat_btn(btn_bar, "Choose Image File…", icon_name="folder", bg=Theme.SURFACE2, fg=Theme.TEXT, hover_bg=Theme.BORDER,
                        command=self.browse_image_file, font=("Segoe UI", 9, "bold")).pack(side="left")

        create_flat_btn(btn_bar, "Apply Thumbnail", icon_name="check", bg=Theme.ACCENT, fg="#ffffff", hover_bg=Theme.ACCENT2,
                        command=self.apply_thumbnail, font=("Segoe UI", 10, "bold")).pack(side="right")

        create_flat_btn(btn_bar, "Cancel", bg=Theme.SURFACE2, fg=Theme.TEXT_DIM, hover_bg=Theme.BORDER,
                        command=self.destroy, font=("Segoe UI", 9)).pack(side="right", padx=(0, 8))

    def _load_initial_image(self):
        # Try loading current existing cover from file
        existing = get_file_cover(self.filepath, self.media_type)
        if existing:
            self.set_image(existing)
        else:
            # Show empty placeholder and prompt to browse
            self._render_placeholder()

    def _render_placeholder(self):
        self.canvas.delete("all")
        self.canvas.create_text(
            self.canvas_w // 2, self.canvas_h // 2 - 20,
            text="No cover art found for this file.", font=("Segoe UI", 12), fill=Theme.TEXT_DIM
        )
        self.canvas.create_text(
            self.canvas_w // 2, self.canvas_h // 2 + 15,
            text="Click 'Choose Image File…' below to pick a photo.", font=("Segoe UI", 9), fill="#60a5fa"
        )
        self._draw_overlay()

    def set_image(self, pil_image):
        self.orig_image = pil_image.convert("RGB")
        self.fit_to_crop_frame()

    def browse_image_file(self):
        ft = [
            ("Image Files", "*.jpg *.jpeg *.png *.webp *.bmp *.gif"),
            ("JPEG Images", "*.jpg *.jpeg"),
            ("PNG Images", "*.png"),
            ("All Files", "*.*")
        ]
        chosen = filedialog.askopenfilename(title="Select Thumbnail Image", filetypes=ft, parent=self)
        if chosen and os.path.exists(chosen):
            try:
                loaded = Image.open(chosen)
                self.set_image(loaded)
            except Exception as e:
                messagebox.showerror("Error Opening Image", f"Could not load image:\n{e}", parent=self)

    def fit_to_crop_frame(self):
        if not self.orig_image:
            return
        ow, oh = self.orig_image.size
        scale_x = self.crop_w / ow
        scale_y = self.crop_h / oh
        self.scale = max(scale_x, scale_y)  # Cover the crop window fully
        self.offset_x = 0
        self.offset_y = 0
        self.zoom_var.set(100)
        self.zoom_val_lbl.config(text="100%")
        self.redraw()

    # ── Panning & Zooming ──

    def _on_pan_start(self, event):
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y

    def _on_pan_drag(self, event):
        if not self.orig_image:
            return
        dx = event.x - self.last_mouse_x
        dy = event.y - self.last_mouse_y
        self.offset_x += dx
        self.offset_y += dy
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        self.redraw()

    def _on_mousewheel(self, event):
        if not self.orig_image:
            return
        step = 1.1 if event.delta > 0 else 0.9
        self._zoom_step(step)

    def _zoom_step(self, factor):
        if not self.orig_image:
            return
        new_scale = max(0.2, min(8.0, self.scale * factor))
        self.scale = new_scale
        percent = int(self.scale / (max(self.crop_w / self.orig_image.size[0], self.crop_h / self.orig_image.size[1])) * 100)
        self.zoom_var.set(max(30, min(400, percent)))
        self.zoom_val_lbl.config(text=f"{percent}%")
        self.redraw()

    def _on_slider_zoom(self, val):
        if not self.orig_image:
            return
        percent = float(val)
        base_scale = max(self.crop_w / self.orig_image.size[0], self.crop_h / self.orig_image.size[1])
        self.scale = base_scale * (percent / 100.0)
        self.zoom_val_lbl.config(text=f"{int(percent)}%")
        self.redraw()

    # ── Drawing ──

    def redraw(self):
        if not self.orig_image:
            return
        self.canvas.delete("all")

        ow, oh = self.orig_image.size
        disp_w = max(1, int(ow * self.scale))
        disp_h = max(1, int(oh * self.scale))

        center_x = (self.cx0 + self.cx1) // 2 + self.offset_x
        center_y = (self.cy0 + self.cy1) // 2 + self.offset_y
        img_x0 = center_x - disp_w // 2
        img_y0 = center_y - disp_h // 2

        # Resize for display preview
        try:
            resized_disp = self.orig_image.resize((disp_w, disp_h), Image.Resampling.BILINEAR)
            self._disp_photo = ImageTk.PhotoImage(resized_disp)
            self.canvas.create_image(img_x0, img_y0, anchor="nw", image=self._disp_photo)
        except Exception:
            pass

        self._draw_overlay()

    def _draw_overlay(self):
        # 1. Darkened outer borders
        self.canvas.create_rectangle(0, 0, self.canvas_w, self.cy0, fill="#050505", stipple="gray50", width=0)
        self.canvas.create_rectangle(0, self.cy1, self.canvas_w, self.canvas_h, fill="#050505", stipple="gray50", width=0)
        self.canvas.create_rectangle(0, self.cy0, self.cx0, self.cy1, fill="#050505", stipple="gray50", width=0)
        self.canvas.create_rectangle(self.cx1, self.cy0, self.canvas_w, self.cy1, fill="#050505", stipple="gray50", width=0)

        # 2. Rule of thirds guideline grid
        gx1 = self.cx0 + self.crop_w // 3
        gx2 = self.cx0 + (self.crop_w * 2) // 3
        gy1 = self.cy0 + self.crop_h // 3
        gy2 = self.cy0 + (self.crop_h * 2) // 3
        self.canvas.create_line(gx1, self.cy0, gx1, self.cy1, fill="#3b82f6", dash=(2, 4))
        self.canvas.create_line(gx2, self.cy0, gx2, self.cy1, fill="#3b82f6", dash=(2, 4))
        self.canvas.create_line(self.cx0, gy1, self.cx1, gy1, fill="#3b82f6", dash=(2, 4))
        self.canvas.create_line(self.cx0, gy2, self.cx1, gy2, fill="#3b82f6", dash=(2, 4))

        # 3. Highlighted Crop Box Outline
        self.canvas.create_rectangle(self.cx0, self.cy0, self.cx1, self.cy1, outline="#3b82f6", width=2)

    # ── Crop & Apply ──

    def apply_thumbnail(self):
        if not self.orig_image:
            messagebox.showinfo("No Image", "Please choose an image file first.", parent=self)
            return

        ow, oh = self.orig_image.size
        disp_w = max(1, int(ow * self.scale))
        disp_h = max(1, int(oh * self.scale))

        center_x = (self.cx0 + self.cx1) // 2 + self.offset_x
        center_y = (self.cy0 + self.cy1) // 2 + self.offset_y
        img_x0 = center_x - disp_w // 2
        img_y0 = center_y - disp_h // 2

        # Relative coordinates on displayed image
        rx0 = (self.cx0 - img_x0) / disp_w
        ry0 = (self.cy0 - img_y0) / disp_h
        rx1 = (self.cx1 - img_x0) / disp_w
        ry1 = (self.cy1 - img_y0) / disp_h

        target_out_w, target_out_h = (600, 600) if self.media_type == "audio" else (160, 120)
        output_crop = Image.new("RGB", (target_out_w, target_out_h), color=(0, 0, 0))

        box_x0 = int(rx0 * ow)
        box_y0 = int(ry0 * oh)
        box_x1 = int(rx1 * ow)
        box_y1 = int(ry1 * oh)

        src_x0 = max(0, box_x0)
        src_y0 = max(0, box_y0)
        src_x1 = min(ow, box_x1)
        src_y1 = min(oh, box_y1)

        span_w = max(1, box_x1 - box_x0)
        span_h = max(1, box_y1 - box_y0)

        if src_x1 > src_x0 and src_y1 > src_y0:
            sub = self.orig_image.crop((src_x0, src_y0, src_x1, src_y1))
            dst_x0 = int((src_x0 - box_x0) / span_w * target_out_w)
            dst_y0 = int((src_y0 - box_y0) / span_h * target_out_h)
            dst_w = max(1, int((src_x1 - src_x0) / span_w * target_out_w))
            dst_h = max(1, int((src_y1 - src_y0) / span_h * target_out_h))
            sub_resized = sub.resize((dst_w, dst_h), Image.Resampling.LANCZOS)
            output_crop.paste(sub_resized, (dst_x0, dst_y0))

        try:
            update_media_cover(self.filepath, self.media_type, output_crop)
            self.on_applied()
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error Saving Thumbnail", f"Failed to save thumbnail:\n{e}", parent=self)
