import pyautogui
import time
import math
import random
import threading
from pynput import keyboard
import pygetwindow as gw
import os
import subprocess

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
pyautogui.FAILSAFE = True  # Move mouse to corner to abort
pyautogui.MINIMUM_DURATION = 0.1
pyautogui.MINIMUM_SLEEP = 0.05

# ── WINDOW TITLE MAPPINGS ─────────────────────────────────────────────────────
# Maps app identifiers to common window title substrings
WINDOW_TITLE_MAPPINGS = {
    "notepad": "Notepad",
    "code": "Visual Studio Code",
    "vscode": "Visual Studio Code",
    "chrome": "Google Chrome",
    "edge": "Microsoft Edge",
    "explorer": "File Explorer",
    "calculator": "Calculator",
    "spotify": "Spotify",
    "whatsapp": "WhatsApp"
}

class AutomationController:
    def __init__(self):
        self._stop_event = threading.Event()
        self._listener = None
        self.is_active = False
        self.current_state = "IDLE"
        self._start_fail_safe()

    # ── FAIL-SAFE SYSTEM ──────────────────────────────────────────────────────
    def _start_fail_safe(self):
        """Listens for the ESC key to immediately stop all automation."""
        def on_press(key):
            if key == keyboard.Key.esc:
                print("\n[!!!] EMERGENCY STOP TRIGGERED [!!!]")
                self.abort()
        
        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.daemon = True
        self._listener.start()

    def abort(self):
        """Stops the current automation sequence."""
        self._stop_event.set()
        self.is_active = False
        self.current_state = "IDLE"
        # Optional: Add a voice feedback here or signal to jarvis.py

    # ── MOUSE ENGINE ─────────────────────────────────────────────────────────
    def move_to(self, x, y, duration=0.5):
        """Moves the mouse smoothly using a custom easing function."""
        if self._stop_event.is_set(): return
        
        print(f"--> Automation: Moving to ({x}, {y})")
        
        # Human-like movement parameters
        start_x, start_y = pyautogui.position()
        
        # Implement a basic ease-in-out movement
        steps = int(duration * 60) # 60fps-ish
        if steps < 1: steps = 1
        
        for i in range(steps + 1):
            if self._stop_event.is_set(): break
            
            t = i / steps
            # Quadratic ease-in-out
            if t < 0.5:
                ease = 2 * t * t
            else:
                ease = -1 + (4 - 2 * t) * t
                
            curr_x = start_x + (x - start_x) * ease
            curr_y = start_y + (y - start_y) * ease
            
            pyautogui.moveTo(curr_x, curr_y)
            time.sleep(duration / steps)

    def click(self, x=None, y=None, button='left', clicks=1):
        """Moves and clicks at the specified coordinates."""
        if self._stop_event.is_set(): return
        
        if x is not None and y is not None:
            self.move_to(x, y)
        
        if self._stop_event.is_set(): return
        
        print(f"--> Automation: Clicking {button} at {pyautogui.position()}")
        pyautogui.click(button=button, clicks=clicks, interval=0.1)
        time.sleep(0.2) # Post-click delay

    def scroll(self, amount):
        """Scrolls the screen by the given amount."""
        if self._stop_event.is_set(): return
        print(f"--> Automation: Scrolling {amount}")
        pyautogui.scroll(amount)

    # ── KEYBOARD ENGINE ───────────────────────────────────────────────────────
    def type_text(self, text, interval=0.05):
        """Types text with natural delays."""
        if self._stop_event.is_set(): return
        
        print(f"--> Automation: Typing '{text}'")
        for char in text:
            if self._stop_event.is_set(): break
            pyautogui.write(char)
            # Add subtle randomness to typing speed
            time.sleep(interval + random.uniform(0, 0.05))

    def press_key(self, key):
        """Presses a specific key or hotkey."""
        if self._stop_event.is_set(): return
        print(f"--> Automation: Pressing {key}")
        pyautogui.press(key)

    def hotkey(self, *keys):
        """Presses a combination of keys."""
        if self._stop_event.is_set(): return
        print(f"--> Automation: Hotkey {keys}")
        pyautogui.hotkey(*keys)

    # ── WINDOW MANAGEMENT ─────────────────────────────────────────────────────
    def get_active_window_title(self):
        try:
            active_window = gw.getActiveWindow()
            return active_window.title if active_window else "Unknown"
        except:
            return "Unknown"

    def focus_window(self, title_part):
        """Attempts to find and activate a window containing the title_part."""
        if self._stop_event.is_set(): return False
        
        # Normalize title_part using mappings if available
        search_title = WINDOW_TITLE_MAPPINGS.get(title_part.lower(), title_part)
        
        print(f"--> Automation: [DEBUG] Attempting to focus window: '{search_title}'")
        try:
            windows = gw.getWindowsWithTitle(search_title)
            if windows:
                win = windows[0]
                if win.isMinimized:
                    win.restore()
                win.activate()
                time.sleep(0.5) # Wait for focus to settle
                print(f"--> Automation: [SUCCESS] Focused window: '{win.title}'")
                return True
            print(f"--> Automation: [FAILED] No window found with title: '{search_title}'")
            return False
        except Exception as e:
            print(f"--> Automation: [ERROR] Focus error: {e}")
            return False

    def wait_for_window(self, title_part, timeout=10):
        """Waits for a window with the given title to appear and be active."""
        if self._stop_event.is_set(): return False
        print(f"--> Automation: [DEBUG] Waiting for window: '{title_part}' (timeout={timeout}s)")
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._stop_event.is_set(): return False
            if self.focus_window(title_part):
                return True
            time.sleep(1.0)
        print(f"--> Automation: [TIMEOUT] Window '{title_part}' did not appear.")
        return False

    def open_file(self, path):
        """Opens a file or folder reliably using os.startfile."""
        if self._stop_event.is_set(): return False
        print(f"--> Automation: [DEBUG] Opening file/path: '{path}'")
        try:
            if os.path.exists(path):
                os.startfile(path)
                print(f"--> Automation: [SUCCESS] File opened: '{path}'")
                return True
            print(f"--> Automation: [FAILED] Path does not exist: '{path}'")
            return False
        except Exception as e:
            print(f"--> Automation: [ERROR] Open error: {e}")
            return False

    def ensure_ready_for_typing(self, title_part=None):
        """Ensures the window is focused and ready for input."""
        if self._stop_event.is_set(): return False
        if title_part:
            if not self.wait_for_window(title_part):
                return False
        
        # Click at current position or a safe spot to ensure focus inside the window
        print("--> Automation: [DEBUG] Ensuring focus for typing (click center of window)")
        try:
            win = gw.getActiveWindow()
            if win:
                # Click slightly below the title bar
                cx, cy = win.center
                self.click(cx, cy + 50) 
                time.sleep(0.3)
                return True
        except:
            pass
        return False

    def verify_focus(self, title_part):
        """Verifies if the current active window matches the title_part."""
        active = self.get_active_window_title().lower()
        return title_part.lower() in active

    # ── DISPATCHER ────────────────────────────────────────────────────────────
    def execute_sequence(self, actions):
        """
        Executes a list of automation actions.
        Schema: [{"type": "move", "x": 100, "y": 200}, {"type": "click"}]
        """
        self._stop_event.clear()
        self.is_active = True
        self.current_state = "EXECUTING"
        
        try:
            for action in actions:
                if self._stop_event.is_set(): break
                
                a_type = action.get("type")
                if a_type == "move":
                    self.move_to(action["x"], action["y"])
                elif a_type == "click":
                    self.click(action.get("x"), action.get("y"), 
                               button=action.get("button", "left"),
                               clicks=action.get("clicks", 1))
                elif a_type == "type":
                    self.type_text(action["text"])
                elif a_type == "press":
                    self.press_key(action["key"])
                elif a_type == "hotkey":
                    self.hotkey(*action["keys"])
                elif a_type == "scroll":
                    self.scroll(action["amount"])
                elif a_type == "wait":
                    time.sleep(action.get("duration", 1.0))
                
                print(f"--> Automation: [STEP SUCCESS] {a_type} completed.")
                time.sleep(0.3) # Natural delay between steps
                
        except Exception as e:
            print(f"--> Automation Error: {e}")
        finally:
            self.is_active = False
            self.current_state = "IDLE"

# Global instance
automation = AutomationController()
