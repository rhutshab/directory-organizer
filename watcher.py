import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import config
import shared

# --- CONSTANTS ---
TEMP_EXTENSIONS = ('.crdownload', '.part', '.tmp', '.download', '.opdownload')
MARKER_STREAM = ":OrganizerTag"


# --- THE BULLETPROOF DOWNLOAD FILTER ---
def is_internet_download(file_path):
    """
    Returns True ONLY if the file is a genuinely new, completed download from the internet.
    """
    # 1. Exist Check
    if not os.path.exists(file_path) or os.path.isdir(file_path):
        return False

    # 2. The Custom Watermark Check (Long-Term Memory)
    # If we have already processed this file and stamped it, ignore it!
    if os.path.exists(file_path + MARKER_STREAM):
        return False

    # 3. The Stateless Time Delta Check (Is it genuinely NEW?)
    # Using getctime per your preference to strictly ignore old files.
    try:
        file_age_seconds = time.time() - os.path.getctime(file_path)
        if file_age_seconds > 300:
            return False
    except OSError:
        return False

    # 4. The "Save As" Ghost File Check
    try:
        if os.path.getsize(file_path) == 0:
            return False
    except OSError:
        return False

    filename = os.path.basename(file_path)

    # 5. Active Download Extension Check
    if filename.endswith(TEMP_EXTENSIONS):
        return False

    # 6. Local Editor / Temp File Check
    if filename.startswith('.') or filename.startswith('~$') or filename.endswith('.bak'):
        return False

    # 7. OS-Level Internet Tag Check
    zone_path = file_path + ":Zone.Identifier"
    if not os.path.exists(zone_path):
        return False

    try:
        with open(zone_path, 'r', encoding='utf-8', errors='ignore') as f:
            zone_data = f.read()

        if "ZoneId=3" not in zone_data:
            return False

        return True

    except PermissionError:
        return False
    except Exception as e:
        print(f"Unexpected error reading Zone Data for {filename}: {e}")
        return False


# --- THE STAMPING FUNCTION ---
def mark_as_processed(file_path):
    """Stamps the file with an invisible custom Alternate Data Stream."""
    try:
        with open(file_path + MARKER_STREAM, 'w') as f:
            f.write("1")
    except Exception as e:
        print(f"Could not stamp file: {e}")


# --- STATE (Ephemeral Session Cache) ---
recent_files = {}
observer = Observer()


# --- HANDLER ---
class DownloadHandler(FileSystemEventHandler):
    def process_file(self, file_path):
        if shared.is_paused:
            return

        # 1. The 3-Second Shield (Absorbs the Watermark Echo)
        current_time = time.time()
        if file_path in recent_files and (current_time - recent_files[file_path] < 3.0):
            return

        # 2. The Gauntlet (Checks for Watermarks, Extensions, ZoneId, etc.)
        if not is_internet_download(file_path):
            return

        # 3. Activate the Shield! (We survived the gauntlet)
        recent_files[file_path] = current_time

        # 4. Apply the invisible OS watermark
        mark_as_processed(file_path)

        # 5. Success! Send it to the UI thread
        shared.file_queue.put(file_path)

    # The Watchdog Triggers
    def on_created(self, event):
        self.process_file(event.src_path)

    def on_moved(self, event):
        self.process_file(event.dest_path)

    def on_modified(self, event):
        self.process_file(event.src_path)


# --- OBSERVER CONTROLS ---
def start_observer():
    global observer
    if observer.is_alive():
        observer.stop()
        observer.join()



    recent_files = {}
    handler = DownloadHandler()

    for folder in config.MONITORED_FOLDERS:
        if os.path.exists(folder):
            observer.schedule(handler, folder, recursive=False)

    observer.start()


def stop_observer():
    if observer.is_alive():
        observer.stop()
        observer.join()