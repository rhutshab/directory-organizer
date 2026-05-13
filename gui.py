import os
import shutil
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import config
import watcher


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
        success = False

        for i in range(10):
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
            messagebox.showerror("Timeout Error", "Failed to move file after 10 attempts.")
            window.destroy()

    except Exception as e:
        messagebox.showerror("Move Error", f"An unexpected error occurred:\n{e}")
        window.destroy()


def show_popup(root, file_path):
    popup = tk.Toplevel(root)
    popup.title("Route File")
    popup.attributes("-topmost", True)
    popup.minsize(350, 100)

    filename = os.path.basename(file_path)
    ttk.Label(popup, text="New file detected:", font=("Segoe UI", 9)).pack(pady=(15, 0))
    ttk.Label(popup, text=filename, font=("Segoe UI", 10, "bold"), wraplength=300, justify="center").pack(pady=(0, 15))

    for name, path in config.CATEGORIES.items():
        ttk.Button(
            popup, text=name, command=lambda p=path: move_file(file_path, p, popup)
        ).pack(fill='x', padx=25, pady=3)

    ttk.Separator(popup, orient='horizontal').pack(fill='x', padx=25, pady=15)
    ttk.Button(popup, text="+ Add New Category",
               command=lambda: [popup.destroy(), show_add_category_window(root, file_path)]).pack(fill='x', padx=25,
                                                                                                  pady=3)
    ttk.Button(popup, text="Ignore", command=popup.destroy).pack(fill='x', padx=25, pady=(3, 15))


def show_add_category_window(root, reprocess_file=None):
    win = tk.Toplevel(root)
    win.title("Add Category")
    win.attributes("-topmost", True)
    win.geometry("380x270")

    ttk.Label(win, text="1. Category Name:", font=("Segoe UI", 9)).pack(pady=(15, 2), padx=20, anchor='w')
    name_entry = ttk.Entry(win)
    name_entry.pack(fill='x', padx=20, pady=2)

    ttk.Label(win, text="2. Destination Folder:", font=("Segoe UI", 9)).pack(pady=(10, 2), padx=20, anchor='w')
    path_var = tk.StringVar()
    path_frame = ttk.Frame(win)
    path_frame.pack(fill='x', padx=20)

    ttk.Entry(path_frame, textvariable=path_var, state='readonly').pack(side='left', fill='x', expand=True)
    ttk.Button(path_frame, text="Browse", width=8,
               command=lambda: path_var.set(filedialog.askdirectory(parent=win, title="Select Folder"))).pack(
        side='right', padx=(5, 0))

    # --- NEW: The Cancel/Back Logic ---
    def go_back():
        win.destroy()
        # If we came here from a file download, bring that routing window back!
        if reprocess_file:
            show_popup(root, reprocess_file)

    # Tell Windows to run our `go_back` function if they click the red 'X' to close the window
    win.protocol("WM_DELETE_WINDOW", go_back)

    def save():
        name, path = name_entry.get().strip(), path_var.get().strip()
        if name and path:
            config.CATEGORIES[name] = path
            config.save_config()
            win.destroy()

            if reprocess_file:
                show_popup(root, reprocess_file)
            else:
                messagebox.showinfo("Success", f"Added '{name}' category!", parent=root)
        else:
            messagebox.showerror("Error", "Provide both name and folder.", parent=win)

    # --- NEW: Side-by-Side Button Layout ---
    btn_frame = ttk.Frame(win)
    btn_frame.pack(pady=20)

    ttk.Button(btn_frame, text="Cancel / Back", command=go_back).pack(side='left', padx=10, ipadx=5)
    ttk.Button(btn_frame, text="Save Category", command=save).pack(side='left', padx=10, ipadx=5)


def show_manage_folders_window(root):
    win = tk.Toplevel(root)
    win.title("Monitored Folders")
    win.attributes("-topmost", True)
    win.geometry("450x290")

    ttk.Label(win, text="Folders currently being watched:", font=("Segoe UI", 10, "bold")).pack(pady=(15, 5))

    listbox = tk.Listbox(win, font=("Segoe UI", 9), height=6, relief="solid", borderwidth=1)
    listbox.pack(fill='x', padx=20, pady=5)

    for folder in config.MONITORED_FOLDERS:
        listbox.insert(tk.END, folder)

    btn_frame = ttk.Frame(win)
    btn_frame.pack(pady=10)

    def add_folder():
        new_folder = filedialog.askdirectory(parent=win, title="Select Folder to Monitor")
        if new_folder and new_folder not in config.MONITORED_FOLDERS:
            config.MONITORED_FOLDERS.append(new_folder)
            listbox.insert(tk.END, new_folder)
            config.save_config()
            watcher.start_observer()

    def remove_folder():
        selected = listbox.curselection()
        if selected:
            folder = listbox.get(selected)
            config.MONITORED_FOLDERS.remove(folder)
            listbox.delete(selected)
            config.save_config()
            watcher.start_observer()

    ttk.Button(btn_frame, text="+ Add Folder", command=add_folder).pack(side='left', padx=10)
    ttk.Button(btn_frame, text="- Remove Selected", command=remove_folder).pack(side='left', padx=10)