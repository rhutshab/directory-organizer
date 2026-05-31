import threading
import queue
import tkinter as tk
from tkinter import ttk
import pystray
from PIL import Image, ImageDraw

# Fix Blurry Windows
try:
    from ctypes import windll

    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# Import our custom modules
import shared
import watcher
import gui


def check_queue():
    try:
        file_path = shared.file_queue.get_nowait()
        gui.show_popup(root, file_path)
    except queue.Empty:
        pass

    try:
        cmd = shared.ui_queue.get_nowait()
        if cmd == "OPEN_ADD_UI":
            gui.show_add_category_window(root)
        elif cmd == "OPEN_MANAGE_FOLDERS_UI":
            gui.show_manage_folders_window(root)
    except queue.Empty:
        pass

    root.after(500, check_queue)


def create_image():
    image = Image.new('RGB', (64, 64), color=(0, 120, 215))
    d = ImageDraw.Draw(image)
    d.ellipse((16, 16, 48, 48), outline="white", width=4)
    return image


def toggle_pause(icon, item):
    shared.is_paused = not shared.is_paused
    icon.notify(f"Organizer is now {'Paused' if shared.is_paused else 'Active'}")


def quit_app(icon, item):
    icon.stop()
    watcher.stop_observer()
    root.quit()


if __name__ == "__main__":
    # Initialize the main hidden window
    root = tk.Tk()
    root.withdraw()

    style = ttk.Style()
    style.theme_use('vista')

    # Start the watchdog background thread
    watcher.start_observer()

    # Build the System Tray
    tray_menu = pystray.Menu(
        pystray.MenuItem("Add Category...", lambda: shared.ui_queue.put("OPEN_ADD_UI")),
        pystray.MenuItem("Manage Monitored Folders...", lambda: shared.ui_queue.put("OPEN_MANAGE_FOLDERS_UI")),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(lambda text: "Resume" if shared.is_paused else "Pause", toggle_pause),
        pystray.MenuItem("Quit", quit_app)
    )

    icon = pystray.Icon("DirOrganizer", create_image(), "Directory Organizer", tray_menu)

    # Start the System tray on its own thread
    threading.Thread(target=icon.run, daemon=True).start()

    # Start checking for files and loop forever
    root.after(500, check_queue)
    root.mainloop()