import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import config
import shared

TEMP_EXTENSIONS = ('.crdownload', '.part', '.tmp', '.download')
recent_files = {}
observer = Observer()


class DownloadHandler(FileSystemEventHandler):
    def process_file(self, file_path):
        if shared.is_paused:
            return
        if os.path.isdir(file_path) or file_path.endswith(TEMP_EXTENSIONS):
            return

        current_time = time.time()
        if file_path in recent_files and (current_time - recent_files[file_path] < 2.0):
            return

        recent_files[file_path] = current_time
        # Send path to the main UI thread via the shared queue
        shared.file_queue.put(file_path)

    def on_created(self, event):
        self.process_file(event.src_path)

    def on_moved(self, event):
        self.process_file(event.dest_path)


def start_observer():
    global observer
    if observer.is_alive():
        observer.stop()
        observer.join()

    observer = Observer()
    handler = DownloadHandler()

    for folder in config.MONITORED_FOLDERS:
        if os.path.exists(folder):
            observer.schedule(handler, folder, recursive=False)

    observer.start()


def stop_observer():
    if observer.is_alive():
        observer.stop()
        observer.join()