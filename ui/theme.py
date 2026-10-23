class Theme:
    is_dark = True
    BG = "#121212"
    SURFACE = "#1e1e1e"
    SURFACE2 = "#2d2d30"
    BORDER = "#3f3f46"
    ACCENT = "#3b82f6"
    ACCENT2 = "#f97316"
    TEXT = "#f3f4f6"
    TEXT_DIM = "#9ca3af"
    SUCCESS = "#22c55e"
    ERROR = "#ef4444"
    WARN = "#f59e0b"

    @classmethod
    def set_theme(cls, is_dark):
        cls.is_dark = is_dark
        if is_dark:
            cls.BG       = "#121212"  
            cls.SURFACE  = "#1e1e1e"  
            cls.SURFACE2 = "#2d2d30"  
            cls.BORDER   = "#3f3f46"  
            cls.ACCENT   = "#3b82f6"  
            cls.ACCENT2  = "#f97316"  
            cls.TEXT     = "#f3f4f6"  
            cls.TEXT_DIM = "#9ca3af"  
            cls.SUCCESS  = "#22c55e"  
            cls.ERROR    = "#ef4444"  
            cls.WARN     = "#f59e0b"  
        else:
            cls.BG       = "#ededed"  
            cls.SURFACE  = "#ffffff"  
            cls.SURFACE2 = "#f1f5f9"  
            cls.BORDER   = "#d1d5db"  
            cls.ACCENT   = "#2191d1"  
            cls.ACCENT2  = "#f97316"  
            cls.TEXT     = "#000000"  
            cls.TEXT_DIM = "#4b5563"  
            cls.SUCCESS  = "#16a34a"  
            cls.ERROR    = "#dc2626"  
            cls.WARN     = "#d97706"  

Theme.set_theme(True)

FONT_TITLE  = ("Segoe UI", 22, "bold")
FONT_BODY   = ("Segoe UI", 10)
FONT_SMALL  = ("Segoe UI", 8)
FONT_MONO   = ("Consolas", 9)
FONT_BTN    = ("Segoe UI", 10, "bold")
FONT_TAB    = ("Segoe UI", 10, "bold")
