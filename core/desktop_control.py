import os
import re
import webbrowser
import pyautogui
from pathlib import Path

# =========================
# 🧠 SMART FILE SEARCH (fallback)
# =========================
SEARCH_PATHS = [
    "C:\\Users",
    "D:\\",
    "E:\\"
]

# =========================
# 📁 WELL-KNOWN FOLDERS + DRIVES
# ("open desktop", "open downloads", "open c drive" used to fall
# straight through to the app shortcut dict and fail - these are
# checked first now, before open_app()'s hardcoded list.)
# =========================
WELL_KNOWN_FOLDERS = {
    "desktop": lambda: str(Path.home() / "Desktop"),
    "downloads": lambda: str(Path.home() / "Downloads"),
    "documents": lambda: str(Path.home() / "Documents"),
    "pictures": lambda: str(Path.home() / "Pictures"),
    "music": lambda: str(Path.home() / "Music"),
    "videos": lambda: str(Path.home() / "Videos"),
}


def open_named_folder(name: str):
    """Return an open_path() result for a well-known folder name, or
    None if `name` isn't one of them (caller should keep trying other
    strategies)."""
    key = name.strip().lower()
    if key in WELL_KNOWN_FOLDERS:
        return open_path(WELL_KNOWN_FOLDERS[key]())
    return None


def open_drive(text: str):
    """Match phrases like 'c drive', 'open d drive', or 'e:' and open
    that drive's root. Returns None if no drive letter is mentioned."""
    match = re.search(r'\b([a-zA-Z])\s*(?:drive|:)', text.lower())
    if match:
        letter = match.group(1).upper()
        return open_path(f"{letter}:\\")
    return None


def find_file_or_folder(name: str):
    name = name.lower()

    for base in SEARCH_PATHS:
        for root, dirs, files in os.walk(base):
            try:
                for d in dirs:
                    if name in d.lower():
                        return os.path.join(root, d)

                for f in files:
                    if name in f.lower():
                        return os.path.join(root, f)
            except Exception:
                continue

    return None


def open_smart(name: str):
    path = find_file_or_folder(name)

    if path:
        os.startfile(path)
        return f"Opening {name}"
    else:
        return f"I couldn't find {name}"


# =========================
# 🪟 WINDOW CONTROL
# =========================
def switch_window():
    try:
        pyautogui.keyDown("alt")
        pyautogui.press("tab")
        pyautogui.keyUp("alt")
        return "Switched window."
    except Exception:
        return "Failed to switch window."


def switch_window_back():
    try:
        pyautogui.keyDown("alt")
        pyautogui.keyDown("shift")
        pyautogui.press("tab")
        pyautogui.keyUp("shift")
        pyautogui.keyUp("alt")
        return "Switched to previous window."
    except Exception:
        return "Failed to switch window."


def show_all_windows():
    try:
        pyautogui.hotkey("win", "tab")
        return "Showing all windows."
    except Exception:
        return "Failed to open task view."


def minimize_all():
    try:
        pyautogui.hotkey("win", "d")
        return "Minimized everything."
    except Exception:
        return "Failed to minimize."


def close_window():
    try:
        pyautogui.hotkey("alt", "f4")
        return "Closed window."
    except Exception:
        return "Failed to close window."


def close_app(name: str):
    """Force-close a named process, e.g. 'chrome' -> chrome.exe."""
    name = name.strip().lower().replace(".exe", "")
    if not name:
        return close_window()
    try:
        os.system(f"taskkill /f /im {name}.exe")
        return f"Closing {name}"
    except Exception:
        return f"Failed to close {name}"


# =========================
# 🖥️ OPEN APPLICATIONS
# =========================
def open_app(app_name: str):
    app_name = app_name.lower()

    apps = {
        "chrome": "start chrome",
        "browser": "start chrome",
        "notepad": "notepad",
        "cmd": "start cmd",
        "command prompt": "start cmd",
        "powershell": "start powershell",
        "explorer": "explorer",
        "file manager": "explorer",
        "vs code": "code",
        "spotify": "start spotify"
    }

    for key in apps:
        if key in app_name:
            os.system(apps[key])
            return f"Opening {key}..."

    return "I couldn't find that application."


# =========================
# 📂 OPEN FILES / FOLDERS
# =========================
def open_path(path: str):
    try:
        if os.path.exists(path):
            os.startfile(path)
            return "Opening it now."
        else:
            return "That path does not exist."
    except Exception:
        return "Failed to open that."


# =========================
# 🌐 WEB / SEARCH
# =========================
def open_website(query: str):
    url = f"https://www.google.com/search?q={query}"
    webbrowser.open(url)
    return f"Searching for {query}"


def search_google(query: str):
    webbrowser.open(f"https://www.google.com/search?q={query}")
    return f"Searching {query}"


# =========================
# ⌨️ INPUT CONTROL
# =========================
def type_text(text):
    try:
        pyautogui.write(text)
        return "Typed"
    except Exception:
        return "Failed to type"


def play_pause():
    try:
        pyautogui.press("playpause")
        return "Done"
    except Exception:
        return "Failed"


# =========================
# 🔊 VOLUME CONTROL
# =========================

def volume_up():
    for _ in range(5):
        pyautogui.press("volumeup")
    return "Volume increased."


def volume_down():
    for _ in range(5):
        pyautogui.press("volumedown")
    return "Volume decreased."


# =========================
# ⚡ WINDOWS POWER CONTROL
# (Server/app lifecycle - stop_server - now lives in
#  core/server_control.py, since that's not a Windows action.)
# =========================
def restart():
    os.system("shutdown /r /t 5")
    return "Restarting in 5 seconds."


def sleep_pc():
    os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
    return "Going to sleep."


def cancel_shutdown():
    """Cancels a pending Windows restart scheduled by restart() above."""
    try:
        os.system("shutdown /a")
        return "Restart cancelled."
    except Exception:
        return "Nothing to cancel."
