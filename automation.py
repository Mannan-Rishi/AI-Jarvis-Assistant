import webbrowser
import os
import pyautogui
import subprocess
import shutil
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
import datetime
import requests
import feedparser

import pywhatkit

def open_youtube(query=None):
    if query:
        pywhatkit.playonyt(query)
    else:
        webbrowser.open("https://www.youtube.com")

def open_google(query=None):
    if query:
        webbrowser.open(f"https://www.google.com/search?q={query}")
    else:
        webbrowser.open("https://www.google.com")

def open_whatsapp():
    webbrowser.open("https://web.whatsapp.com")

# ── APP NORMALIZATION ─────────────────────────────────────────────────────────
APP_MAPPINGS = {
    "notepad": "notepad.exe",
    "calc": "calc.exe",
    "calculator": "calc.exe",
    "explorer": "explorer.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "taskmgr": "taskmgr.exe",
    "task manager": "taskmgr.exe",
    "settings": "start ms-settings:",
    "control": "control.exe",
    "control panel": "control.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "code": "code.cmd",
    "vs code": "code.cmd",
    "visual studio code": "code.cmd",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "whatsapp": "whatsapp.exe",
    "spotify": "spotify.exe"
}

def find_app_path(app_name):
    """Attempts to find the executable path for a given app name."""
    # 1. Check mapping
    exe = APP_MAPPINGS.get(app_name.lower(), app_name)
    
    # 2. Check system PATH
    path = shutil.which(exe)
    if path: return path
    
    # 3. Common paths (Not exhaustive but covers many basics)
    common_paths = [
        os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), exe),
        os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), exe),
        os.path.join(os.environ.get("LocalAppData", ""), "Programs", exe),
    ]
    for p in common_paths:
        if os.path.exists(p): return p
        if not p.endswith(".exe") and os.path.exists(p + ".exe"): return p + ".exe"
    
    return exe # Return original as last resort

def open_app(app_name):
    """Reliably launches an application."""
    try:
        app_name_lower = app_name.lower().strip()
        print(f"--> Automation: [DEBUG] Attempting to launch app: '{app_name_lower}'")

        # 1. Folders Check
        folders = {
            "downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
            "documents": os.path.join(os.path.expanduser("~"), "Documents"),
            "pictures": os.path.join(os.path.expanduser("~"), "Pictures"),
            "videos": os.path.join(os.path.expanduser("~"), "Videos"),
            "music": os.path.join(os.path.expanduser("~"), "Music"),
            "desktop": os.path.join(os.path.expanduser("~"), "Desktop")
        }
        if app_name_lower in folders:
            os.startfile(folders[app_name_lower])
            return True

        # 2. Websites Check
        websites = {
            "chatgpt": "https://chat.openai.com",
            "github": "https://github.com",
            "gmail": "https://mail.google.com",
            "facebook": "https://facebook.com",
            "instagram": "https://instagram.com",
            "twitter": "https://twitter.com",
            "linkedin": "https://linkedin.com",
            "amazon": "https://amazon.com",
            "netflix": "https://netflix.com",
            "youtube": "https://youtube.com"
        }
        if app_name_lower in websites:
            webbrowser.open(websites[app_name_lower])
            return True

        # 3. App Launch Logic
        target = find_app_path(app_name_lower)
        
        if target.startswith("start "): # Handle ms-settings etc.
            os.system(target)
            return True
            
        # Launch using subprocess or os.startfile
        try:
            subprocess.Popen(target, shell=True)
            print(f"--> Automation: [SUCCESS] Launched via Popen: '{target}'")
        except:
            os.startfile(target)
            print(f"--> Automation: [SUCCESS] Launched via startfile: '{target}'")
            
        return True
    except Exception as e:
        print(f"--> Automation: [ERROR] Failed to open '{app_name}': {e}")
        return False

def open_folder(path):
    try:
        os.startfile(path)
        return True
    except Exception as e:
        print(f"Error opening folder: {e}")
        return False

def take_screenshot():
    try:
        from config import SCREENSHOT_PATH
        # Ensure directory exists just in case
        if not os.path.exists(SCREENSHOT_PATH):
            os.makedirs(SCREENSHOT_PATH)
            
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = os.path.join(SCREENSHOT_PATH, f"screenshot_{timestamp}.png")
        
        print(f"--> Automation: [DEBUG] Taking screenshot: {filename}")
        pyautogui.screenshot(filename)
        
        if os.path.exists(filename):
            print(f"--> Automation: [SUCCESS] Screenshot saved: {filename}")
            return filename
        else:
            print("--> Automation: [ERROR] PyAutoGUI did not save the file.")
            return None
    except Exception as e:
        print(f"--> Automation: [ERROR] Screenshot failed: {e}")
        return None

def set_volume(level):
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        
        # level is 0 to 100
        # set_master_volume_level_scalar takes 0.0 to 1.0
        volume.SetMasterVolumeLevelScalar(level / 100, None)
        return True
    except Exception as e:
        print(f"Volume error: {e}")
        return False

def get_weather(city="London"):
    try:
        # Using wttr.in for free weather
        res = requests.get(f"https://wttr.in/{city}?format=3")
        return res.text.strip()
    except:
        return "Weather data nahi mil raha, Sir."

def get_news():
    try:
        # BBC Top Stories RSS Feed
        feed = feedparser.parse("http://feeds.bbci.co.uk/news/rss.xml")
        headlines = []
        for entry in feed.entries[:3]: # Get top 3
            headlines.append(entry.title)
        return "Aaj ki top headlines ye hain: " + ". ".join(headlines)
    except Exception as e:
        print(f"News error: {e}")
        return "Abhi news feed access nahi ho rahi, Sir."

# =============================================================================
#  SAFE FILE SYSTEM LAYER
# =============================================================================
import os as _os

_KNOWN_DIRS = {
    'desktop':   _os.path.join(_os.path.expanduser('~'), 'Desktop'),
    'downloads': _os.path.join(_os.path.expanduser('~'), 'Downloads'),
    'documents': _os.path.join(_os.path.expanduser('~'), 'Documents'),
    'music':     _os.path.join(_os.path.expanduser('~'), 'Music'),
    'videos':    _os.path.join(_os.path.expanduser('~'), 'Videos'),
    'pictures':  _os.path.join(_os.path.expanduser('~'), 'Pictures'),
    'temp':      _os.environ.get('TEMP', _os.path.expanduser('~')),
}

_BLOCKED = {
    _os.environ.get('SystemRoot', 'C:\\Windows').lower(),
    'c:\\windows', 'c:\\program files', 'c:\\program files (x86)',
    'c:\\perflogs', 'c:\\system volume information'
}

def resolve_path(raw):
    if not raw: return _KNOWN_DIRS['desktop']
    parts = raw.replace('\\', '/').split('/')
    first = parts[0].lower().strip()
    if first in _KNOWN_DIRS:
        base = _KNOWN_DIRS[first]
        rest = parts[1:]
        return _os.path.join(base, *rest) if rest else base
    if _os.path.isabs(raw): return raw
    return _os.path.join(_KNOWN_DIRS['desktop'], raw)

def is_safe_path(path):
    p = _os.path.abspath(path).lower()
    return not any(p == b or p.startswith(b + _os.sep) for b in _BLOCKED)

def create_folder(path):
    try:
        full = resolve_path(path)
        _os.makedirs(full, exist_ok=True)
        print(f'--> FS: Created folder: {full}')
        return full
    except Exception as e:
        print(f'--> FS Error (create_folder): {e}'); return ''

def create_file(path):
    try:
        full = resolve_path(path)
        if not _os.path.splitext(full)[1]: full += '.txt'
        _os.makedirs(_os.path.dirname(full), exist_ok=True)
        if not _os.path.exists(full): open(full, 'w', encoding='utf-8').close()
        print(f'--> FS: Created file: {full}')
        return full
    except Exception as e:
        print(f'--> FS Error (create_file): {e}'); return ''

def write_file(path, content):
    try:
        full = resolve_path(path)
        if not _os.path.splitext(full)[1]: full += '.txt'
        _os.makedirs(_os.path.dirname(full), exist_ok=True)
        with open(full, 'w', encoding='utf-8') as f: f.write(content)
        print(f'--> FS: Wrote to: {full}')
        return full
    except Exception as e:
        print(f'--> FS Error (write_file): {e}'); return ''

def append_file(path, content):
    try:
        full = resolve_path(path)
        if not _os.path.splitext(full)[1]: full += '.txt'
        _os.makedirs(_os.path.dirname(full), exist_ok=True)
        with open(full, 'a', encoding='utf-8') as f: f.write('\n' + content)
        print(f'--> FS: Appended to: {full}')
        return full
    except Exception as e:
        print(f'--> FS Error (append_file): {e}'); return ''

def erase_file(path):
    try:
        full = resolve_path(path)
        if not _os.path.exists(full): return ''
        open(full, 'w', encoding='utf-8').close()
        print(f'--> FS: Erased: {full}')
        return full
    except Exception as e:
        print(f'--> FS Error (erase_file): {e}'); return ''

def _remove_readonly(func, path, exc_info):
    """Callback for shutil.rmtree to remove read-only attributes and retry."""
    import stat
    try:
        _os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass

def delete_path(path):
    import shutil
    import stat
    import time
    try:
        full = resolve_path(path)
        if not _os.path.exists(full): return 'not_found'
        if not is_safe_path(full):
            print(f'--> FS: BLOCKED deletion: {full}'); return 'blocked'
            
        attempts = 2
        for attempt in range(attempts):
            try:
                if _os.path.isdir(full):
                    shutil.rmtree(full, onerror=_remove_readonly)
                else:
                    try:
                        _os.remove(full)
                    except PermissionError:
                        # Unlock file permissions
                        _os.chmod(full, stat.S_IWRITE)
                        _os.remove(full)
                print(f'--> FS: Deleted: {full}')
                return full
            except Exception as e:
                if attempt < attempts - 1:
                    print(f'--> FS: File in use, retrying in 1s...')
                    time.sleep(1)
                else:
                    print(f'--> FS Error (delete_path): {e}')
                    return ''
    except Exception as e:
        print(f'--> FS Error (delete_path): {e}'); return ''

def move_path(source, destination):
    import shutil
    try:
        src  = resolve_path(source)
        dest = resolve_path(destination)
        if not _os.path.exists(src): return 'not_found'
        _os.makedirs(dest if _os.path.isdir(dest) else _os.path.dirname(dest), exist_ok=True)
        shutil.move(src, dest)
        print(f'--> FS: Moved {src} -> {dest}')
        return dest
    except Exception as e:
        print(f'--> FS Error (move_path): {e}'); return ''
