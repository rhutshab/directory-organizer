import os
import shutil
import queue
import threading
import time
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import pystray
from PIL import Image, ImageDraw

# --- NEW: Fix Blurry Windows on High DPI Displays ---
try:
    from ctypes import windll

    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# --- CONFIGURATION & PERSISTENCE ---
TEMP_EXTENSIONS = ('.crdownload', '.part', '.tmp', '.download')
CONFIG_FILE = "organizer_config.json"
DEFAULT_DOWNLOADS = os.path.join(os.path.expanduser('~'), 'Downloads')


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        # FIX 1: Start completely empty
        default = {
            "monitored_folders": [DEFAULT_DOWNLOADS],
            "categories": {}
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default, f, indent=4)
        return default


def save_config():
    config_data = {
        "monitored_folders": MONITORED_FOLDERS,
        "categories": CATEGORIES
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_data, f, indent=4)


config = load_config()
MONITORED_FOLDERS = config.get("monitored_folders", [DEFAULT_DOWNLOADS])
CATEGORIES = config.get("categories", {})

# Global State
is_paused = False
file_queue = queue.Queue()
ui_queue = queue.Queue()
recent_files = {}
observer = Observer()


# --- WATCHDOG MANAGEMENT ---
def start_observer():
    global observer
    if observer.is_alive():
        observer.stop()
        observer.join()

    observer = Observer()
    handler = DownloadHandler()

    for folder in MONITORED_FOLDERS:
        if os.path.exists(folder):
            observer.schedule(handler, folder, recursive=False)

    observer.start()


# --- FILE MOVING LOGIC ---
def move_file(source, destination_folder, window):
    for widget in window.winfo_children():
        widget.destroy()

    status_label = ttk.Label(window, text="Moving file...", font=("Segoe UI", 11, "bold"))
    status_label.pack(expand=True)
    window.update()

    try:
        if not os.path.exists(destination_folder):
            os.makedirs(destination_folder)

        final_destination = os.path.join(destination_folder, os.path.basename(source))

        max_retries = 10
        success = False

        for i in range(max_retries):
            try:
                shutil.move(source, final_destination)
                success = True
                break
            except PermissionError:
                status_label.config(text=f"Waiting on Windows...\n(Attempt {i + 1}/10)", foreground="orange")
                window.update()
                time.sleep(1)

        if success:
            status_label.config(text="Success! ✔", foreground="green", font=("Segoe UI", 12, "bold"))
            window.update()
            window.after(1000, window.destroy)
        else:
            messagebox.showerror("Timeout Error",
                                 "Failed to move file after 10 attempts.\nWindows won't release the lock.")
            window.destroy()

    except Exception as e:
        messagebox.showerror("Move Error", f"An unexpected error occurred:\n{e}")
        window.destroy()


# --- GUI (TKINTER) LOGIC ---
def show_popup(file_path):
    popup = tk.Toplevel(root)
    popup.title("Route File")
    popup.attributes("-topmost", True)

    # FIX: Let Windows calculate the height automatically.
    # We only force it to be a nice width (350px).
    popup.minsize(350, 100)

    filename = os.path.basename(file_path)
    ttk.Label(popup, text="New file detected:", font=("Segoe UI", 9)).pack(pady=(15, 0))
    ttk.Label(popup, text=filename, font=("Segoe UI", 10, "bold"), wraplength=300, justify="center").pack(pady=(0, 15))

    # Existing category buttons
    for name, path in CATEGORIES.items():
        ttk.Button(
            popup, text=name, command=lambda p=path: move_file(file_path, p, popup)
        ).pack(fill='x', padx=25, pady=3)

    def open_add_ui():
        popup.destroy()
        show_add_category_window(reprocess_file=file_path)

    # Separator
    ttk.Separator(popup, orient='horizontal').pack(fill='x', padx=25, pady=15)

    # Action buttons (These won't get cut off anymore!)
    ttk.Button(popup, text="+ Add New Category", command=open_add_ui).pack(fill='x', padx=25, pady=3)
    ttk.Button(popup, text="Ignore", command=popup.destroy).pack(fill='x', padx=25, pady=(3, 15))


def show_add_category_window(reprocess_file=None):
    win = tk.Toplevel(root)
    win.title("Add Category")
    win.attributes("-topmost", True)
    win.geometry("380x230")

    ttk.Label(win, text="1. Category Name:", font=("Segoe UI", 9)).pack(pady=(15, 2), padx=20, anchor='w')
    name_entry = ttk.Entry(win)
    name_entry.pack(fill='x', padx=20, pady=2)

    ttk.Label(win, text="2. Destination Folder:", font=("Segoe UI", 9)).pack(pady=(10, 2), padx=20, anchor='w')
    path_var = tk.StringVar()
    path_frame = ttk.Frame(win)
    path_frame.pack(fill='x', padx=20)

    ttk.Entry(path_frame, textvariable=path_var, state='readonly').pack(side='left', fill='x', expand=True)

    # FIX 2: Added parent=win to force the dialog to stay on top
    ttk.Button(path_frame, text="Browse", width=8,
               command=lambda: path_var.set(filedialog.askdirectory(parent=win, title="Select Folder"))).pack(
        side='right', padx=(5, 0))

    def save():
        name, path = name_entry.get().strip(), path_var.get().strip()
        if name and path:
            CATEGORIES[name] = path
            save_config()
            win.destroy()

            if reprocess_file:
                show_popup(reprocess_file)
            else:
                messagebox.showinfo("Success", f"Added '{name}' category!", parent=root)
        else:
            messagebox.showerror("Error", "Provide both name and folder.", parent=win)

    ttk.Button(win, text="Save Category", command=save).pack(pady=20, ipadx=10)


def show_manage_folders_window():
    win = tk.Toplevel(root)
    win.title("Monitored Folders")
    win.attributes("-topmost", True)
    win.geometry("450x290")

    ttk.Label(win, text="Folders currently being watched:", font=("Segoe UI", 10, "bold")).pack(pady=(15, 5))

    listbox = tk.Listbox(win, font=("Segoe UI", 9), height=6, relief="solid", borderwidth=1)
    listbox.pack(fill='x', padx=20, pady=5)

    for folder in MONITORED_FOLDERS:
        listbox.insert(tk.END, folder)

    btn_frame = ttk.Frame(win)
    btn_frame.pack(pady=10)

    def add_folder():
        # FIX 2: Added parent=win
        new_folder = filedialog.askdirectory(parent=win, title="Select Folder to Monitor")
        if new_folder and new_folder not in MONITORED_FOLDERS:
            MONITORED_FOLDERS.append(new_folder)
            listbox.insert(tk.END, new_folder)
            save_config()
            start_observer()

    def remove_folder():
        selected = listbox.curselection()
        if selected:
            folder = listbox.get(selected)
            MONITORED_FOLDERS.remove(folder)
            listbox.delete(selected)
            save_config()
            start_observer()

    ttk.Button(btn_frame, text="+ Add Folder", command=add_folder).pack(side='left', padx=10)
    ttk.Button(btn_frame, text="- Remove Selected", command=remove_folder).pack(side='left', padx=10)


def check_queue():
    try:
        file_path = file_queue.get_nowait()
        show_popup(file_path)
    except queue.Empty:
        pass

    try:
        cmd = ui_queue.get_nowait()
        if cmd == "OPEN_ADD_UI":
            show_add_category_window()
        elif cmd == "OPEN_MANAGE_FOLDERS_UI":
            show_manage_folders_window()
    except queue.Empty:
        pass

    root.after(500, check_queue)


# --- WATCHDOG HANDLER ---
class DownloadHandler(FileSystemEventHandler):
    def process_file(self, file_path):
        if is_paused:
            return
        if os.path.isdir(file_path) or file_path.endswith(TEMP_EXTENSIONS):
            return

        current_time = time.time()
        if file_path in recent_files and (current_time - recent_files[file_path] < 2.0):
            return

        recent_files[file_path] = current_time
        file_queue.put(file_path)

    def on_created(self, event):
        self.process_file(event.src_path)

    def on_moved(self, event):
        self.process_file(event.dest_path)


# --- SYSTEM TRAY LOGIC ---
def create_image():
    image = Image.new('RGB', (64, 64), color=(0, 120, 215))
    d = ImageDraw.Draw(image)
    d.ellipse((16, 16, 48, 48), outline="white", width=4)
    return image


tray_menu = pystray.Menu(
    pystray.MenuItem("Add Category...", lambda: ui_queue.put("OPEN_ADD_UI")),
    pystray.MenuItem("Manage Monitored Folders...", lambda: ui_queue.put("OPEN_MANAGE_FOLDERS_UI")),
    pystray.Menu.SEPARATOR,
    pystray.MenuItem(lambda text: "Resume" if is_paused else "Pause",
                     lambda icon, item: globals().update(is_paused=not is_paused) or icon.notify(
                         f"Organizer is now {'Paused' if is_paused else 'Active'}")),
    pystray.MenuItem("Quit", lambda icon, item: [icon.stop(), observer.stop(), root.quit()])
)

# --- INITIALIZATION ---
if __name__ == "__main__":
    # Initialize the themed Tkinter root window
    root = tk.Tk()
    root.withdraw()

    # Set the global theme to look native
    style = ttk.Style()
    style.theme_use('vista')  # 'vista' is the closest native theme wrapper on modern Windows

    start_observer()

    icon = pystray.Icon("DirOrganizer", create_image(), "Directory Organizer", tray_menu)
    threading.Thread(target=icon.run, daemon=True).start()

    root.after(500, check_queue)
    root.mainloop()