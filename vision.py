import time
import threading
from PIL import ImageGrab
import pygetwindow as gw
import io
import pyautogui

class VisionEngine:
    def __init__(self, interval=5):
        self.interval = interval
        self._running = False
        self._thread = None
        self.latest_screenshot = None
        self.active_window_title = "Unknown"
        self._lock = threading.Lock()

    def _get_active_window_title(self):
        try:
            active_window = gw.getActiveWindow()
            if active_window is not None:
                return active_window.title
            return "Desktop"
        except Exception:
            return "Unknown"

    def _capture_screen(self):
        try:
            # Capture screen using Pillow
            screen = ImageGrab.grab()
            
            # Optionally compress or resize to save RAM / API payload size
            # Resize by 50% for lower memory usage and faster API upload
            screen.thumbnail((screen.width // 2, screen.height // 2))
            
            return screen
        except Exception as e:
            print(f"Vision Capture Error: {e}")
            return None

    def _vision_loop(self):
        while self._running:
            title = self._get_active_window_title()
            img = self._capture_screen()
            
            with self._lock:
                self.active_window_title = title
                self.latest_screenshot = img

            time.sleep(self.interval)

    def start_passive_mode(self):
        """Starts the passive vision tracking thread."""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._vision_loop, daemon=True)
            self._thread.start()
            print("--> Vision Engine: Passive Mode Started.")

    def stop_passive_mode(self):
        """Stops the passive vision tracking thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            print("--> Vision Engine: Passive Mode Stopped.")

    def get_ui_preview(self):
        """Returns a small, blurred base64 image for the GUI preview."""
        with self._lock:
            if self.latest_screenshot is None:
                return None
            
            # Create a small thumbnail for the UI
            preview = self.latest_screenshot.copy()
            preview.thumbnail((200, 120))
            
            # Convert to base64 to pass to GUI
            buffered = io.BytesIO()
            preview.save(buffered, format="JPEG", quality=50)
            return buffered.getvalue()

    def get_screen_size(self):
        """Returns the actual screen resolution (width, height)."""
        return pyautogui.size()

    def map_coordinates(self, x_pct, y_pct):
        """Maps percentage coordinates (0-100) to actual pixels."""
        w, h = self.get_screen_size()
        x = int((x_pct / 100) * w)
        y = int((y_pct / 100) * h)
        return x, y

    def get_current_context(self):
        """Returns the current active window title and screenshot."""
        with self._lock:
            # If we don't have a screenshot yet (or if passive mode is off), grab one instantly
            if self.latest_screenshot is None:
                self.active_window_title = self._get_active_window_title()
                self.latest_screenshot = self._capture_screen()
            
            return self.active_window_title, self.latest_screenshot

    def get_active_window(self):
        """Fast, lightweight check of current activity without image capture."""
        with self._lock:
            if self.active_window_title != "Unknown":
                return self.active_window_title
            return self._get_active_window_title()

# Global instance
vision = VisionEngine(interval=5)
