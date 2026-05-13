import os
import json

CONFIG_FILE = "organizer_config.json"
DEFAULT_DOWNLOADS = os.path.join(os.path.expanduser('~'), 'Downloads')

CATEGORIES = {}
MONITORED_FOLDERS = []

def load_config():
    global CATEGORIES, MONITORED_FOLDERS
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            CATEGORIES = data.get("categories", {})
            MONITORED_FOLDERS = data.get("monitored_folders", [DEFAULT_DOWNLOADS])
    else:
        CATEGORIES = {}
        MONITORED_FOLDERS = [DEFAULT_DOWNLOADS]
        save_config()

def save_config():
    config_data = {
        "monitored_folders": MONITORED_FOLDERS,
        "categories": CATEGORIES
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_data, f, indent=4)

# Load immediately when this file is imported
load_config()