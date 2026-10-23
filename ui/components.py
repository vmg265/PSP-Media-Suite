import os
import math
import tkinter as tk
import tkinter.font as tkfont
from PIL import Image, ImageTk

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

def create_flat_btn(parent, text="", icon_name=None, width=None, height=32, bg=None, fg=None,
                    hover_bg=None, command=None, font=None, icon_size=16, padx=12, pady=5):
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

        draw_rounded_rect(self, 0, 0, w, h, 8, fill)

        cx = w // 2
        cy = h // 2
        if self._icon_name:
            photo = get_icon_photo(self._icon_name, size=18, color=txt_color)
            self._icon_ref = photo
            self.create_image(cx - 75, cy, image=photo, anchor="center")
            self.create_text(cx + 8, cy, text=self._text, font=("Segoe UI", 10, "bold"), fill=txt_color, anchor="center")
        else:
            self.create_text(cx, cy, text=self._text, font=("Segoe UI", 10, "bold"), fill=txt_color, anchor="center")

class AnimatedBanner(tk.Canvas):
    """
    Iconic PSP & PS3 XMB fluid sine-wave ribbon animation with floating stardust particles.
    Authentically replicates the classic PlayStation 3 and PlayStation Portable XMB wave.
    """

    def __init__(self, parent, height=66):
        super().__init__(parent, bg="#040914", highlightthickness=0, height=height)
        self.t = 0.0
        self._banner_icon = None

        # Floating ambient particles (PS3 XMB dynamic theme)
        self.particles = [
            {
                'x': (i * 49) % 1200,
                'y': (i * 21) % height,
                'speed': 0.35 + (i % 6) * 0.12,
                'size': 1 + (i % 3),
                'phase': i * 0.65,
                'alpha_color': '#38bdf8' if (i % 3 == 0) else ('#0284c7' if (i % 2 == 0) else '#bae6fd')
            }
            for i in range(22)
        ]

        self._load_icon()
        self.bind("<Configure>", lambda e: self.redraw())

    def _load_icon(self):
        icon_path = get_resource_path("Icon.png")
        if os.path.exists(icon_path):
            try:
                img = Image.open(icon_path).resize((40, 40), Image.Resampling.LANCZOS)
                self._banner_icon = ImageTk.PhotoImage(img)
            except Exception:
                self._banner_icon = None

    def tick_animation(self):
        self.t += 0.038
        w = max(self.winfo_width(), 800)
        for p in self.particles:
            p['x'] = (p['x'] + p['speed']) % w
        self.redraw()

    def redraw(self):
        self.delete("wave", "particle", "banner_content")
        w = max(self.winfo_width(), 800)
        h = max(self.winfo_height(), 66)
        mid_y = h * 0.52

        # ── 1. Deep Atmospheric Background Wave Ribbon ──
        steps = 32
        pts_back = []
        for i in range(steps + 1):
            x = (i / steps) * w
            y = mid_y + 15 * math.sin(x * 0.0048 + self.t * 0.72) + 7 * math.cos(x * 0.011 - self.t * 0.45)
            pts_back.extend([x, y - 18])
        for i in range(steps, -1, -1):
            x = (i / steps) * w
            y = mid_y + 15 * math.sin(x * 0.0048 + self.t * 0.72) + 7 * math.cos(x * 0.011 - self.t * 0.45)
            pts_back.extend([x, y + 20])
        self.create_polygon(pts_back, fill="#071b36", smooth=True, outline="", tags="wave")

        # ── 2. Mid PlayStation Signature Blue Ribbon ──
        pts_mid = []
        crest_mid = []
        for i in range(steps + 1):
            x = (i / steps) * w
            y = mid_y + 13 * math.sin(x * 0.0068 + self.t) + 8 * math.cos(x * 0.0135 - self.t * 0.8)
            thick = 12 + 7 * math.sin(x * 0.0055 + self.t * 0.55)
            pts_mid.extend([x, y - thick])
            crest_mid.extend([x, y - thick])
        for i in range(steps, -1, -1):
            x = (i / steps) * w
            y = mid_y + 13 * math.sin(x * 0.0068 + self.t) + 8 * math.cos(x * 0.0135 - self.t * 0.8)
            thick = 12 + 7 * math.sin(x * 0.0055 + self.t * 0.55)
            pts_mid.extend([x, y + thick])
        self.create_polygon(pts_mid, fill="#0a3d78", smooth=True, outline="", tags="wave")
        self.create_line(crest_mid, fill="#1d8cf8", width=1.5, smooth=True, tags="wave")

        # ── 3. Foreground Luminous Electric Cyan Ribbon ──
        pts_fore = []
        crest_fore = []
        for i in range(steps + 1):
            x = (i / steps) * w
            y = mid_y + 10 * math.sin(x * 0.0085 - self.t * 1.25) + 6 * math.sin(x * 0.016 + self.t * 0.95)
            thick = 7 + 5 * math.cos(x * 0.0078 + self.t * 0.65)
            pts_fore.extend([x, y - thick])
            crest_fore.extend([x, y - thick])
        for i in range(steps, -1, -1):
            x = (i / steps) * w
            y = mid_y + 10 * math.sin(x * 0.0085 - self.t * 1.25) + 6 * math.sin(x * 0.016 + self.t * 0.95)
            thick = 7 + 5 * math.cos(x * 0.0078 + self.t * 0.65)
            pts_fore.extend([x, y + thick])
        self.create_polygon(pts_fore, fill="#0077b6", smooth=True, outline="", tags="wave")
        self.create_line(crest_fore, fill="#64d2ff", width=2, smooth=True, tags="wave")

        # ── 4. Floating XMB Stardust Particles ──
        for p in self.particles:
            py = (p['y'] + 6 * math.sin(self.t + p['phase'])) % h
            sz = p['size']
            self.create_oval(p['x'], py, p['x'] + sz, py + sz, fill=p['alpha_color'], outline="", tags="particle")

        # ── 5. Left Branding ──
        tx = 20
        if self._banner_icon:
            self.create_image(22, h // 2, anchor="w", image=self._banner_icon, tags="banner_content")
            tx = 72

        self.create_text(
            tx, h // 2, text="PSP MEDIA SUITE",
            font=("Segoe UI", 14, "bold"), fill="#ffffff", anchor="w", tags="banner_content"
        )

        self.tag_lower("particle")
        self.tag_lower("wave")

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
