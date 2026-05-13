import os
import shutil
import queue
import threading
import tkinter as tk
from tkinter import messagebox
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import pystray
from PIL import Image, ImageDraw
import time

# --- CONFIGURATION ---
TEMP_EXTENSIONS = ('.crdownload', '.part', '.tmp', '.download')
DOWNLOAD_DIR = os.path.join(os.path.expanduser('~'), 'Downloads')
recent_files = {}
# Replace these with your actual RUET/Work paths
# Use the 'r' prefix and absolute paths for your C: or D: drive
CATEGORIES = {
    "Memes": r"C:\Users\utsha\Downloads\Memes",
    "Academics": r"D:\Academics",
    "Work": r"D:\Work",
    "Software": r"C:\Users\utsha\Downloads\Programs"
}

# Global State
is_paused = False
file_queue = queue.Queue()


# --- FILE MOVING LOGIC ---
def move_file(source, destination_folder, window):
    # 1. Clear the existing buttons and text from the popup
    for widget in window.winfo_children():
        widget.destroy()

    # 2. Add a status label and force the window to visually update
    status_label = tk.Label(window, text="Moving file...", font=("Arial", 12, "bold"))
    status_label.pack(expand=True)
    window.update()

    try:
        # Create directory if missing
        if not os.path.exists(destination_folder):
            os.makedirs(destination_folder)

        final_destination = os.path.join(destination_folder, os.path.basename(source))

        # The Patient Retry Loop
        max_retries = 10
        success = False

        for i in range(max_retries):
            try:
                shutil.move(source, final_destination)
                success = True
                break
            except PermissionError:
                # Update the label so you know it's waiting on Windows Defender
                status_label.config(text=f"Waiting for Windows to release file...\n(Attempt {i + 1}/10)", fg="orange")
                window.update()
                time.sleep(1)

        if success:
            # 3. Show Success and Auto-Close!
            status_label.config(text="Success! ✔", fg="green", font=("Arial", 14, "bold"))
            window.update()
            # Wait 1000 milliseconds (1 second) then destroy the window
            window.after(1000, window.destroy)
        else:
            # Only pop up a second window if it critically fails
            messagebox.showerror("Timeout Error",
                                 f"Failed to move file after 10 attempts.\nWindows won't release the lock.")
            window.destroy()

    except Exception as e:
        messagebox.showerror("Move Error", f"An unexpected error occurred:\n{e}")
        window.destroy()

# --- GUI (TKINTER) LOGIC ---
def show_popup(file_path):
    # Create a secondary window (Toplevel) attached to the hidden root
    popup = tk.Toplevel(root)
    popup.title("Route File")
    popup.attributes("-topmost", True)
    popup.geometry("300x250")

    filename = os.path.basename(file_path)
    tk.Label(popup, text="New file downloaded:", font=("Arial", 10)).pack(pady=(10, 0))
    tk.Label(popup, text=filename, font=("Arial", 10, "bold"), wraplength=280).pack(pady=(0, 10))

    for name, path in CATEGORIES.items():
        tk.Button(
            popup,
            text=name,
            command=lambda p=path: move_file(file_path, p, popup)
        ).pack(fill='x', padx=20, pady=2)

    tk.Button(popup, text="Ignore", command=popup.destroy).pack(fill='x', padx=20, pady=10)


def check_queue():
    """Silently checks if watchdog found a file. Runs every 500ms."""
    try:
        file_path = file_queue.get_nowait()
        show_popup(file_path)
    except queue.Empty:
        pass
    # Schedule this function to run again in 500ms
    root.after(500, check_queue)


# --- WATCHDOG LOGIC ---
class DownloadHandler(FileSystemEventHandler):
    def process_file(self, file_path):
        if is_paused:
            return
        if os.path.isdir(file_path) or file_path.endswith(TEMP_EXTENSIONS):
            return

        # --- DEBOUNCE LOGIC ---
        current_time = time.time()
        # If we saw this exact file less than 2 seconds ago, ignore it
        if file_path in recent_files and (current_time - recent_files[file_path] < 2.0):
            return

        recent_files[file_path] = current_time
        # Send to Tkinter via the thread-safe queue
        file_queue.put(file_path)

    def on_created(self, event):
        self.process_file(event.src_path)

    def on_moved(self, event):
        self.process_file(event.dest_path)


# --- SYSTEM TRAY LOGIC ---
def create_image():
    """Generates a simple 64x64 blue icon with a white 'O' for the system tray."""
    image = Image.new('RGB', (64, 64), color=(0, 120, 215))  # Windows Blue
    d = ImageDraw.Draw(image)
    d.ellipse((16, 16, 48, 48), outline="white", width=4)
    return image


def toggle_pause(icon, item):
    global is_paused
    is_paused = not is_paused
    icon.notify(f"Organizer is now {'Paused' if is_paused else 'Active'}")


def quit_app(icon, item):
    icon.stop()
    observer.stop()
    root.quit()  # Kills the main Tkinter loop


# Build the right-click menu
tray_menu = pystray.Menu(
    pystray.MenuItem(lambda text: "Resume" if is_paused else "Pause", toggle_pause),
    pystray.MenuItem("Quit", quit_app)
)

# --- INITIALIZATION ---
if __name__ == "__main__":
    # 1. Setup Watchdog (Background Thread)
    observer = Observer()
    observer.schedule(DownloadHandler(), DOWNLOAD_DIR, recursive=False)
    observer.start()

    # 2. Setup System Tray (Background Thread)
    icon = pystray.Icon("DirOrganizer", create_image(), "Directory Organizer", tray_menu)
    threading.Thread(target=icon.run, daemon=True).start()

    # 3. Setup Tkinter (Main Thread)
    root = tk.Tk()
    root.withdraw()  # Hide the main window permanently

    # Start the queue polling loop
    root.after(500, check_queue)

    # Block the main thread with Tkinter's event loop
    root.mainloop()