"""
PSP Media Suite
A media sync application to convert and load music, music playlists, and videos
onto a USB-connected PSP or wirelessly via an embedded PSP web browser download server.
"""

import tkinter as tk
from ui.main_window import PSPMediaSuite

def main():
    root = tk.Tk()
    app = PSPMediaSuite(root)
    root.mainloop()

if __name__ == "__main__":
    main()
