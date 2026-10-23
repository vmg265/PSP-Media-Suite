"""
Google Material Icon Pack renderer for PSP Media Suite.
Draws crisp, anti-aliased vector symbols directly with PIL at any size/color,
with caching for high-performance Tkinter PhotoImages.
No emojis - 100% clean Google Material icons.
"""

import math
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk

_ICON_CACHE = {}

def render_vector_icon(name, size=24, color='#ffffff'):
    """Renders a Google Material Symbol as an anti-aliased PIL RGBA Image."""
    s = size * 4
    im = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    stroke = max(2, int(s * 0.08))

    if name == 'menu':
        for y_rel in [0.28, 0.50, 0.72]:
            y = int(s * y_rel)
            d.line([s * 0.18, y, s * 0.82, y], fill=color, width=stroke)

    elif name == 'music_note':
        stem_x = int(s * 0.65)
        d.line([stem_x, s * 0.22, stem_x, s * 0.65], fill=color, width=stroke)
        d.ellipse([s * 0.28, s * 0.52, stem_x + stroke//2, s * 0.78], fill=color)
        d.polygon([(stem_x - stroke//2, s * 0.22), (s * 0.85, s * 0.32), (s * 0.85, s * 0.44), (stem_x - stroke//2, s * 0.34)], fill=color)

    elif name == 'movie':
        d.rounded_rectangle([s * 0.15, s * 0.20, s * 0.85, s * 0.80], radius=int(s * 0.08), outline=color, width=stroke)
        d.line([s * 0.15, s * 0.40, s * 0.85, s * 0.40], fill=color, width=stroke)
        d.polygon([(s * 0.44, s * 0.48), (s * 0.62, s * 0.60), (s * 0.44, s * 0.72)], fill=color)

    elif name == 'queue_music':
        for y_rel in [0.28, 0.50, 0.72]:
            y = int(s * y_rel)
            d.line([s * 0.15, y, s * 0.58, y], fill=color, width=stroke)
        stem_x = int(s * 0.80)
        d.line([stem_x, s * 0.35, stem_x, s * 0.70], fill=color, width=stroke)
        d.ellipse([s * 0.62, s * 0.62, stem_x + stroke//2, s * 0.82], fill=color)
        d.line([stem_x - stroke//2, s * 0.35, s * 0.92, s * 0.42], fill=color, width=stroke)

    elif name == 'search':
        cr = s * 0.28
        cx, cy = s * 0.42, s * 0.42
        d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], outline=color, width=stroke)
        d.line([cx + cr * 0.7, cy + cr * 0.7, s * 0.86, s * 0.86], fill=color, width=int(stroke * 1.3))

    elif name in ('sync', 'refresh'):
        d.arc([s * 0.20, s * 0.20, s * 0.80, s * 0.80], start=40, end=320, fill=color, width=stroke)
        d.polygon([(s * 0.80, s * 0.46), (s * 0.66, s * 0.42), (s * 0.76, s * 0.30)], fill=color)

    elif name == 'folder':
        d.polygon([(s * 0.15, s * 0.26), (s * 0.44, s * 0.26), (s * 0.52, s * 0.36), (s * 0.85, s * 0.36),
                   (s * 0.85, s * 0.76), (s * 0.15, s * 0.76)], outline=color, width=stroke)

    elif name == 'image':
        d.rounded_rectangle([s * 0.16, s * 0.20, s * 0.84, s * 0.80], radius=int(s * 0.08), outline=color, width=stroke)
        d.ellipse([s * 0.30, s * 0.32, s * 0.44, s * 0.46], fill=color)
        d.polygon([(s * 0.24, s * 0.72), (s * 0.46, s * 0.48), (s * 0.60, s * 0.62), (s * 0.76, s * 0.44), (s * 0.76, s * 0.72)], fill=color)

    elif name == 'edit':
        d.polygon([(s * 0.22, s * 0.78), (s * 0.36, s * 0.76), (s * 0.76, s * 0.36), (s * 0.64, s * 0.24), (s * 0.24, s * 0.64)], outline=color, width=stroke)
        d.line([s * 0.22, s * 0.78, s * 0.30, s * 0.70], fill=color, width=stroke)

    elif name == 'delete':
        d.line([s * 0.20, s * 0.28, s * 0.80, s * 0.28], fill=color, width=stroke)
        d.line([s * 0.40, s * 0.20, s * 0.60, s * 0.20], fill=color, width=stroke)
        d.polygon([(s * 0.28, s * 0.28), (s * 0.72, s * 0.28), (s * 0.68, s * 0.82), (s * 0.32, s * 0.82)], outline=color, width=stroke)
        d.line([s * 0.42, s * 0.40, s * 0.42, s * 0.70], fill=color, width=stroke//2 + 1)
        d.line([s * 0.58, s * 0.40, s * 0.58, s * 0.70], fill=color, width=stroke//2 + 1)

    elif name == 'check':
        d.line([s * 0.22, s * 0.52, s * 0.42, s * 0.74], fill=color, width=int(stroke * 1.4))
        d.line([s * 0.40, s * 0.74, s * 0.82, s * 0.28], fill=color, width=int(stroke * 1.4))

    elif name == 'close':
        d.line([s * 0.25, s * 0.25, s * 0.75, s * 0.75], fill=color, width=int(stroke * 1.3))
        d.line([s * 0.75, s * 0.25, s * 0.25, s * 0.75], fill=color, width=int(stroke * 1.3))

    elif name == 'public':
        d.ellipse([s * 0.18, s * 0.18, s * 0.82, s * 0.82], outline=color, width=stroke)
        d.line([s * 0.18, s * 0.50, s * 0.82, s * 0.50], fill=color, width=stroke)
        d.ellipse([s * 0.34, s * 0.18, s * 0.66, s * 0.82], outline=color, width=stroke)

    elif name == 'stop':
        d.rounded_rectangle([s * 0.26, s * 0.26, s * 0.74, s * 0.74], radius=int(s * 0.08), fill=color)

    elif name == 'article':
        d.rounded_rectangle([s * 0.22, s * 0.16, s * 0.78, s * 0.84], radius=int(s * 0.06), outline=color, width=stroke)
        for y_rel in [0.36, 0.50, 0.64]:
            y = int(s * y_rel)
            d.line([s * 0.34, y, s * 0.66, y], fill=color, width=stroke)

    elif name == 'grid_view':
        gap = int(s * 0.08)
        sz = int(s * 0.26)
        r = int(s * 0.04)
        x0, y0 = int(s * 0.20), int(s * 0.20)
        d.rounded_rectangle([x0, y0, x0 + sz, y0 + sz], radius=r, fill=color)
        d.rounded_rectangle([x0 + sz + gap, y0, x0 + sz * 2 + gap, y0 + sz], radius=r, fill=color)
        d.rounded_rectangle([x0, y0 + sz + gap, x0 + sz, y0 + sz * 2 + gap], radius=r, fill=color)
        d.rounded_rectangle([x0 + sz + gap, y0 + sz + gap, x0 + sz * 2 + gap, y0 + sz * 2 + gap], radius=r, fill=color)

    elif name == 'view_list':
        for y_rel in [0.30, 0.50, 0.70]:
            y = int(s * y_rel)
            d.ellipse([s * 0.18, y - stroke, s * 0.18 + stroke * 2, y + stroke], fill=color)
            d.line([s * 0.36, y, s * 0.82, y], fill=color, width=stroke)

    elif name == 'upload':
        d.line([s * 0.50, s * 0.68, s * 0.50, s * 0.24], fill=color, width=stroke)
        d.polygon([(s * 0.50, s * 0.20), (s * 0.32, s * 0.38), (s * 0.68, s * 0.38)], fill=color)
        d.line([s * 0.22, s * 0.80, s * 0.78, s * 0.80], fill=color, width=stroke)

    elif name == 'copy':
        d.rounded_rectangle([s * 0.32, s * 0.32, s * 0.82, s * 0.82], radius=int(s * 0.06), outline=color, width=stroke)
        d.polygon([(s * 0.20, s * 0.68), (s * 0.20, s * 0.20), (s * 0.68, s * 0.20)], outline=color, width=stroke)

    elif name == 'settings':
        d.ellipse([s * 0.35, s * 0.35, s * 0.65, s * 0.65], outline=color, width=stroke)
        for ang in range(0, 360, 45):
            rad = math.radians(ang)
            x0 = s * 0.50 + math.cos(rad) * s * 0.28
            y0 = s * 0.50 + math.sin(rad) * s * 0.28
            x1 = s * 0.50 + math.cos(rad) * s * 0.40
            y1 = s * 0.50 + math.sin(rad) * s * 0.40
            d.line([x0, y0, x1, y1], fill=color, width=int(stroke * 1.2))

    elif name == 'hourglass':
        d.polygon([(s * 0.24, s * 0.22), (s * 0.76, s * 0.22), (s * 0.50, s * 0.50)], outline=color, width=stroke)
        d.polygon([(s * 0.50, s * 0.50), (s * 0.76, s * 0.78), (s * 0.24, s * 0.78)], outline=color, width=stroke)

    elif name == 'info':
        d.ellipse([s * 0.18, s * 0.18, s * 0.82, s * 0.82], outline=color, width=stroke)
        d.ellipse([s * 0.45, s * 0.32, s * 0.55, s * 0.42], fill=color)
        d.line([s * 0.50, s * 0.48, s * 0.50, s * 0.68], fill=color, width=stroke)

    elif name == 'add':
        d.line([s * 0.50, s * 0.22, s * 0.50, s * 0.78], fill=color, width=stroke)
        d.line([s * 0.22, s * 0.50, s * 0.78, s * 0.50], fill=color, width=stroke)

    elif name == 'arrow_up':
        d.line([s * 0.50, s * 0.76, s * 0.50, s * 0.28], fill=color, width=stroke)
        d.polygon([(s * 0.50, s * 0.20), (s * 0.30, s * 0.42), (s * 0.70, s * 0.42)], fill=color)

    elif name == 'arrow_down':
        d.line([s * 0.50, s * 0.24, s * 0.50, s * 0.72], fill=color, width=stroke)
        d.polygon([(s * 0.50, s * 0.80), (s * 0.30, s * 0.58), (s * 0.70, s * 0.58)], fill=color)

    elif name == 'save':
        d.rounded_rectangle([s * 0.20, s * 0.20, s * 0.80, s * 0.80], radius=int(s * 0.06), outline=color, width=stroke)
        d.rectangle([s * 0.34, s * 0.20, s * 0.66, s * 0.40], fill=color)
        d.rectangle([s * 0.30, s * 0.54, s * 0.70, s * 0.80], outline=color, width=max(1, stroke // 2))

    elif name == 'zoom_in':
        cr = s * 0.26
        cx, cy = s * 0.40, s * 0.40
        d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], outline=color, width=stroke)
        d.line([cx + cr * 0.7, cy + cr * 0.7, s * 0.84, s * 0.84], fill=color, width=int(stroke * 1.3))
        d.line([cx - cr * 0.45, cy, cx + cr * 0.45, cy], fill=color, width=stroke)
        d.line([cx, cy - cr * 0.45, cx, cy + cr * 0.45], fill=color, width=stroke)

    return im.resize((size, size), Image.Resampling.LANCZOS)

def get_icon_photo(name, size=20, color='#ffffff'):
    """Returns a cached ImageTk.PhotoImage for the requested Google Material Icon."""
    key = (name, size, color)
    if key not in _ICON_CACHE:
        pil_img = render_vector_icon(name, size, color)
        _ICON_CACHE[key] = ImageTk.PhotoImage(pil_img)
    return _ICON_CACHE[key]

def create_icon_btn(parent, icon_name, text="", command=None, bg="#27272a", fg="#ffffff",
                    hover_bg="#3f3f46", font=("Segoe UI", 9), icon_size=16, icon_color=None,
                    padx=10, pady=5):
    """
    Creates a modern flat button with a Google Material Icon and optional text.
    Handles hover states and click events cleanly.
    """
    ic_col = icon_color or fg
    photo = get_icon_photo(icon_name, size=icon_size, color=ic_col)

    compound_mode = "left" if text else "center"
    btn = tk.Label(
        parent, image=photo, text=("  " + text) if text else "",
        compound=compound_mode, font=font, fg=fg, bg=bg,
        anchor="center", cursor="hand2", padx=padx, pady=pady
    )
    btn.image = photo  # keep reference
    btn._bg = bg
    btn._hover_bg = hover_bg

    btn.bind("<Enter>", lambda e: btn.config(bg=btn._hover_bg))
    btn.bind("<Leave>", lambda e: btn.config(bg=btn._bg))
    if command:
        btn.bind("<Button-1>", lambda e: command())
    return btn
