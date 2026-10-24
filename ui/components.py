import os
import math
import tkinter as tk
import tkinter.font as tkfont
from PIL import Image, ImageTk, ImageDraw, ImageFilter

from ui.theme import Theme, FONT_BTN, FONT_TAB, FONT_SMALL
from core.config import get_resource_path
from ui.icons import get_icon_photo

def draw_rounded_rect(canvas, x0, y0, x1, y1, r, color, outline=""):
    """Draws a smooth anti-aliased rounded rectangle on a Tkinter Canvas."""
    canvas.create_arc(x0, y0, x0 + r * 2, y0 + r * 2, start=90,  extent=90, fill=color, outline=outline)
    canvas.create_arc(x1 - r * 2, y0, x1, y0 + r * 2, start=0,   extent=90, fill=color, outline=outline)
    canvas.create_arc(x0, y1 - r * 2, x0 + r * 2, y1, start=180, extent=90, fill=color, outline=outline)
    canvas.create_arc(x1 - r * 2, y1 - r * 2, x1, y1, start=270, extent=90, fill=color, outline=outline)
    canvas.create_rectangle(x0 + r, y0, x1 - r, y1, fill=color, outline=outline)
    canvas.create_rectangle(x0, y0 + r, x1, y1 - r, fill=color, outline=outline)

class SimpleTooltip:
    """Lightweight tooltip that appears when hovering over a widget."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self._after_id = None
        self.widget.bind("<Enter>", self._on_enter, add="+")
        self.widget.bind("<Leave>", self._on_leave, add="+")
        self.widget.bind("<ButtonPress>", self._on_leave, add="+")

    def _on_enter(self, event=None):
        self._cancel()
        self._after_id = self.widget.after(300, self.show_tip)

    def _on_leave(self, event=None):
        self._cancel()
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None

    def _cancel(self):
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def show_tip(self):
        if not self.widget.winfo_exists():
            return
        x = self.widget.winfo_rootx() + (self.widget.winfo_width() // 2)
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        try:
            tw.attributes("-topmost", True)
        except Exception:
            pass
        lbl = tk.Label(tw, text=self.text, font=("Segoe UI", 8), bg="#18181b", fg="#ffffff",
                       highlightbackground=Theme.BORDER, highlightthickness=1, padx=6, pady=3)
        lbl.pack()
        tw.update_idletasks()
        req_w = lbl.winfo_reqwidth()
        tw.wm_geometry(f"+{max(0, x - (req_w // 2))}+{y}")

def create_flat_btn(parent, text="", icon_name=None, width=None, height=32, bg=None, fg=None,
                    hover_bg=None, command=None, font=None, icon_size=16, padx=12, pady=5,
                    tooltip=None):
    """Creates a modern flat button with optional Google Material Icon and hover effect."""
    bg = bg or Theme.SURFACE2
    fg = fg or Theme.TEXT
    hover_bg = hover_bg or Theme.BORDER
    f = font or FONT_BTN

    photo = None
    if icon_name:
        photo = get_icon_photo(icon_name, size=icon_size, color=fg)

    compound = "left" if (photo and text) else ("center" if photo else "none")
    btn = tk.Label(
        parent, text=text, image=photo if photo else "", compound=compound,
        font=f, fg=fg, bg=bg, anchor="center", cursor="hand2", padx=padx, pady=pady
    )
    if photo:
        btn.image = photo
    btn._bg = bg
    btn._hbg = hover_bg
    btn.bind("<Enter>", lambda e: btn.config(bg=btn._hbg))
    btn.bind("<Leave>", lambda e: btn.config(bg=btn._bg))
    if command:
        btn.bind("<Button-1>", lambda e: command())
    if tooltip:
        SimpleTooltip(btn, tooltip)
    return btn

def create_tab_btn(parent, text, tab_id, on_click, icon_name=None):
    """Creates a tab selector button with optional Google Material Icon."""
    photo = None
    if icon_name:
        photo = get_icon_photo(icon_name, size=18, color=Theme.TEXT_DIM)

    btn = tk.Label(
        parent, text=text, image=photo if photo else "", compound="left" if photo else "none",
        font=FONT_TAB, fg=Theme.TEXT_DIM, bg=Theme.SURFACE2, padx=16, pady=8, cursor="hand2"
    )
    if photo:
        btn.image = photo
        btn._icon_name = icon_name

    btn.bind("<Button-1>", lambda e: on_click(tab_id))
    btn._tab_id = tab_id
    return btn

def draw_status_indicator(canvas, status, text=""):
    """Draws a clean Google Material vector status badge (no emojis)."""
    canvas.delete("all")
    w = canvas.winfo_width()
    h = canvas.winfo_height()
    if w <= 1:
        w = 24
    if h <= 1:
        h = 24

    palette = {
        "pending":    (Theme.SURFACE, Theme.TEXT_DIM),
        "processing": (Theme.WARN, "#000000"),
        "success":    (Theme.SUCCESS, "#ffffff"),
        "error":      (Theme.ERROR, "#ffffff")
    }
    bg, fg = palette.get(status, (Theme.SURFACE, Theme.TEXT_DIM))
    draw_rounded_rect(canvas, 1, 1, w - 1, h - 1, 6, bg)

    cx, cy = w // 2, h // 2
    if status == "success":
        photo = get_icon_photo("check", size=14, color=fg)
        canvas.create_image(cx, cy, image=photo)
        canvas._img_ref = photo
    elif status == "error":
        photo = get_icon_photo("close", size=14, color=fg)
        canvas.create_image(cx, cy, image=photo)
        canvas._img_ref = photo
    elif status == "processing":
        photo = get_icon_photo("hourglass", size=13, color=fg)
        canvas.create_image(cx, cy, image=photo)
        canvas._img_ref = photo
    else:
        # Pending: clean small center dot
        canvas.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=fg, outline="")

class AccentButton(tk.Canvas):
    """Canvas-based rounded pill button supporting hover, disabled, and processing states with icon."""

    def __init__(self, parent, text, icon_name=None, width=190, height=44, command=None):
        super().__init__(parent, bg=Theme.SURFACE, highlightthickness=0, width=width, height=height, cursor="hand2")
        self._text = text
        self._icon_name = icon_name
        self._state = "normal"
        self._width = width
        self._height = height
        self._command = command

        self.redraw()
        self.bind("<Configure>", lambda e: self.redraw())
        if command:
            self.bind("<Button-1>", lambda e: self._on_click())
        self.bind("<Enter>", lambda e: self.redraw(hover=True))
        self.bind("<Leave>", lambda e: self.redraw(hover=False))

    def _on_click(self):
        if self._state == "normal" and self._command:
            self._command()

    def set_state(self, text, state="normal"):
        self._text = text
        self._state = state
        self.redraw()

    def redraw(self, hover=False):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1:
            w = self._width
        if h <= 1:
            h = self._height

        if self._state == "disabled":
            fill = Theme.SURFACE2
            txt_color = Theme.TEXT_DIM
        elif self._state == "processing":
            fill = Theme.WARN
            txt_color = "#000000"
        elif hover:
            fill = Theme.ACCENT2
            txt_color = "#ffffff"
        else:
            fill = Theme.ACCENT
            txt_color = "#ffffff"

        # Zero corner radius: sharp flat rectangle matching all other buttons
        self.create_rectangle(0, 0, w, h, fill=fill, outline="")

        cx = w // 2
        cy = h // 2
        if self._icon_name:
            icon_sz = 18
            photo = get_icon_photo(self._icon_name, size=icon_sz, color=txt_color)
            self._icon_ref = photo
            f = tkfont.Font(family="Segoe UI", size=10, weight="bold")
            text_w = f.measure(self._text)
            gap = 8
            total_w = icon_sz + gap + text_w
            start_x = max(4, (w - total_w) // 2)
            icon_x = start_x + (icon_sz // 2)
            text_x = start_x + icon_sz + gap + (text_w // 2)
            self.create_image(icon_x, cy, image=photo, anchor="center")
            self.create_text(text_x, cy, text=self._text, font=f, fill=txt_color, anchor="center")
        else:
            self.create_text(cx, cy, text=self._text, font=("Segoe UI", 10, "bold"), fill=txt_color, anchor="center")

class AnimatedBanner(tk.Canvas):
    """
    Iconic PSP & PS3 XMB fluid sine-wave ribbon animation with floating stardust particles.
    Authentically replicates the classic PlayStation 3 and PlayStation Portable XMB wave
    using a true optical Gaussian frosted glass texture for zero pixelation and near-zero CPU usage.
    """

    def __init__(self, parent, height=66):
        super().__init__(parent, bg="#0b1120", highlightthickness=0, height=height)
        self.height = height
        self._banner_icon = None
        self._load_icon()

        # Pre-render seamless frosted glass wave texture (generated once, zero runtime CPU overhead)
        self._texture_w = 1920
        self._texture_h = height
        self._bg_photo = self._generate_frosted_texture(self._texture_w, self._texture_h)
        self.scroll_x = 0.0

        # Persistent canvas items (no object destruction / recreation per tick)
        self._tile1 = self.create_image(0, 0, image=self._bg_photo, anchor="nw", tags="bg_wave")
        self._tile2 = self.create_image(self._texture_w, 0, image=self._bg_photo, anchor="nw", tags="bg_wave")
        self._tile3 = self.create_image(self._texture_w * 2, 0, image=self._bg_photo, anchor="nw", tags="bg_wave")

        # Floating ambient particles (PS3 XMB dynamic theme)
        self.particles = []
        for i in range(16):
            p_x = (i * 83) % 1400
            p_y = (i * 21) % height
            sz = 1 + (i % 3)
            col = '#7dd3fc' if (i % 3 == 0) else ('#38bdf8' if (i % 2 == 0) else '#bae6fd')
            item_id = self.create_oval(p_x, p_y, p_x + sz, p_y + sz, fill=col, outline="", tags="particle")
            self.particles.append({
                'id': item_id,
                'x': float(p_x),
                'y': float(p_y),
                'speed': 0.35 + (i % 5) * 0.12,
                'size': sz,
                'phase': i * 0.75
            })

        # Left Branding items (persistent)
        tx = 20
        if self._banner_icon:
            self._icon_item = self.create_image(22, height // 2, anchor="w", image=self._banner_icon, tags="brand")
            tx = 72
        else:
            self._icon_item = None

        self._text_item = self.create_text(
            tx, height // 2, text="PSP MEDIA SUITE",
            font=("Segoe UI", 14, "bold"), fill="#ffffff", anchor="w", tags="brand"
        )

        self.tag_raise("particle")
        self.tag_raise("brand")
        self.bind("<Configure>", lambda e: self._on_configure())

    def _generate_frosted_texture(self, W, H):
        PAD = 60
        TOTAL_W = W + PAD * 2

        img = Image.new('RGBA', (TOTAL_W, H), (11, 17, 30, 255))
        overlay = Image.new('RGBA', (TOTAL_W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Seamless wave frequencies over width W
        w1 = 2 * math.pi * 2 / W
        w2 = 2 * math.pi * 4 / W
        w3 = 2 * math.pi * 6 / W

        # Layer 1: Ambient deep frosted ocean ribbon
        pts1 = [(x, H * 0.52 + 13 * math.sin((x - PAD) * w1) + 6 * math.cos((x - PAD) * w2)) for x in range(0, TOTAL_W + 4, 4)]
        for i in range(len(pts1) - 1):
            draw.line([pts1[i], pts1[i+1]], fill=(12, 60, 105, 140), width=26)

        # Layer 2: Mid frosted sapphire ribbon
        pts2 = [(x, H * 0.50 + 10 * math.sin((x - PAD) * w2 + 1.2) + 5 * math.cos((x - PAD) * w3)) for x in range(0, TOTAL_W + 4, 4)]
        for i in range(len(pts2) - 1):
            draw.line([pts2[i], pts2[i+1]], fill=(20, 95, 155, 170), width=16)

        # Layer 3: Foreground electric cyan ribbon
        pts3 = [(x, H * 0.48 + 7 * math.sin((x - PAD) * w1 + 2.4) + 4 * math.sin((x - PAD) * w3 + 0.8)) for x in range(0, TOTAL_W + 4, 4)]
        for i in range(len(pts3) - 1):
            draw.line([pts3[i], pts3[i+1]], fill=(56, 189, 248, 210), width=8)

        # Layer 4: Specular crest highlights
        for i in range(len(pts3) - 1):
            draw.line([(pts3[i][0], pts3[i][1] - 2), (pts3[i+1][0], pts3[i+1][1] - 2)], fill=(147, 222, 255, 240), width=3)

        # Apply true optical Gaussian blur for frosted glass diffusion
        blurred = overlay.filter(ImageFilter.GaussianBlur(radius=6))
        composite = Image.alpha_composite(img, blurred)
        seamless = composite.crop((PAD, 0, PAD + W, H))

        # Add frosted glass specular borders
        draw_final = ImageDraw.Draw(seamless)
        draw_final.line([(0, H - 1), (W, H - 1)], fill=(30, 41, 59, 255), width=1)
        draw_final.line([(0, 0), (W, 0)], fill=(30, 58, 92, 160), width=1)

        return ImageTk.PhotoImage(seamless)

    def _load_icon(self):
        icon_path = get_resource_path("Icon.png")
        if os.path.exists(icon_path):
            try:
                img = Image.open(icon_path).resize((40, 40), Image.Resampling.LANCZOS)
                self._banner_icon = ImageTk.PhotoImage(img)
            except Exception:
                self._banner_icon = None

    def tick_animation(self):
        # 1. Update background tile positions with fractional smooth scroll
        self.scroll_x = (self.scroll_x + 0.5) % self._texture_w
        x1 = -int(self.scroll_x)
        x2 = x1 + self._texture_w
        x3 = x2 + self._texture_w
        self.coords(self._tile1, x1, 0)
        self.coords(self._tile2, x2, 0)
        self.coords(self._tile3, x3, 0)

        # 2. Update floating ambient particles (ultra-low CPU coords update)
        w = max(self.winfo_width(), 800)
        h = self.height
        t = self.scroll_x * 0.04
        for p in self.particles:
            p['x'] = (p['x'] + p['speed']) % w
            py = (p['y'] + 5 * math.sin(t + p['phase'])) % (h - 6) + 3
            px = p['x']
            sz = p['size']
            self.coords(p['id'], px, py, px + sz, py + sz)

    def redraw(self):
        self.tick_animation()

    def _on_configure(self):
        self.tag_raise("brand")

class ProgressBar(tk.Canvas):
    """Rounded custom progress bar with animated pulsating PlayStation neon glow."""

    def __init__(self, parent, height=12):
        super().__init__(parent, bg=Theme.SURFACE, highlightthickness=0, height=height)
        self.progress_val = 0
        self.pulse_phase = 0.0
        self.bind("<Configure>", lambda e: self.redraw())

    def update_progress(self, val):
        self.progress_val = max(0, min(100, val))
        self.redraw()

    def tick_pulse(self):
        self.pulse_phase = (self.pulse_phase + 0.09) % (2 * math.pi)
        if self.progress_val > 0:
            self.redraw()

    def _pulse_color(self, base_hex, target_hex):
        t = (1 - math.cos(self.pulse_phase)) / 2
        def lerp(a, b): return int(a + (b - a) * t)
        r1, g1, b1 = int(base_hex[1:3], 16), int(base_hex[3:5], 16), int(base_hex[5:7], 16)
        r2, g2, b2 = int(target_hex[1:3], 16), int(target_hex[3:5], 16), int(target_hex[5:7], 16)
        return f"#{lerp(r1, r2):02x}{lerp(g1, g2):02x}{lerp(b1, b2):02x}"

    def redraw(self):
        w, h = self.winfo_width(), self.winfo_height()
        self.delete("all")
        if w < 4:
            return
        r = h // 2
        draw_rounded_rect(self, 0, 0, w, h, r, Theme.SURFACE2)
        if self.progress_val > 0:
            fill_w = max(r * 2, int(w * self.progress_val / 100))
            color = self._pulse_color(Theme.ACCENT, "#38bdf8")
            draw_rounded_rect(self, 0, 0, fill_w, h, r, color)

class MiniProgressBar(tk.Canvas):
    """Compact rounded pill progress bar used for overall queue multi-item progress."""

    def __init__(self, parent, width=110, height=8):
        super().__init__(parent, bg=Theme.SURFACE, highlightthickness=0, width=width, height=height)
        self._width = width
        self._height = height
        self.progress_val = 0
        self.bind("<Configure>", lambda e: self.redraw())

    def update_progress(self, val):
        self.progress_val = max(0, min(100, val))
        self.redraw()

    def redraw(self):
        w = max(self.winfo_width(), self._width)
        h = max(self.winfo_height(), self._height)
        self.delete("all")
        r = h // 2
        draw_rounded_rect(self, 0, 0, w, h, r, Theme.SURFACE2)
        if self.progress_val > 0:
            fill_w = max(r * 2, int(w * self.progress_val / 100))
            draw_rounded_rect(self, 0, 0, fill_w, h, r, "#38bdf8")

class MarqueeLabel(tk.Canvas):
    """
    Smooth, slow-rotating / horizontal ticker marquee for queue cards and long media titles.
    When text exceeds card width, it smoothly scrolls horizontally back and forth with edge pauses.
    """

    def __init__(self, parent, text, font=("Segoe UI", 9, "bold"), fg="#ffffff", bg="#1f1f23",
                 height=22, width=120):
        super().__init__(parent, bg=bg, highlightthickness=0, height=height, width=width)
        self.text = text
        self.font = font
        self.fg = fg
        self.bg = bg
        self._offset = 0
        self._direction = -1
        self._pause = 30
        self._tk_font = tkfont.Font(font=font)
        self.text_w = self._tk_font.measure(text)

        self.bind("<Configure>", lambda e: self.redraw())
        self.redraw()

    def set_text(self, text):
        self.text = text
        self.text_w = self._tk_font.measure(text)
        self._offset = 0
        self._direction = -1
        self._pause = 30
        self.redraw()

    def redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1:
            w = 120
        if h <= 1:
            h = 22

        if self.text_w <= w:
            # Fits completely: center/align left cleanly without moving
            self.create_text(2, h // 2, text=self.text, font=self.font, fill=self.fg, anchor="w")
        else:
            # Overflow: draw at current marquee offset
            self.create_text(self._offset, h // 2, text=self.text, font=self.font, fill=self.fg, anchor="w")

    def tick(self):
        """Called every frame by the UI animation loop to smoothly tick the marquee."""
        w = self.winfo_width()
        if w <= 1 or self.text_w <= w:
            return

        max_scroll = self.text_w - w + 16
        if self._pause > 0:
            self._pause -= 1
            return

        self._offset += self._direction * 1
        if self._offset <= -max_scroll:
            self._direction = 1
            self._pause = 40  # Pause at the end so user can read last characters
        elif self._offset >= 0:
            self._offset = 0
            self._direction = -1
            self._pause = 40  # Pause at beginning
        self.redraw()
