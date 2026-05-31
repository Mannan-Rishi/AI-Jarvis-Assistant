import os
import json
import threading

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
MEMORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")
LONG_TERM_FILE = os.path.join(MEMORY_DIR, "long_term.json")
MAX_SHORT_TERM_CONTEXT = 15

# Ensure directory exists
os.makedirs(MEMORY_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# LONG-TERM MEMORY (Persistent JSON)
# ─────────────────────────────────────────────────────────────────────────────
class LongTermMemory:
    def __init__(self):
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self):
        if not os.path.exists(LONG_TERM_FILE):
            return {"preferences": {}, "projects": {}, "aliases": {}, "facts": {}}
        try:
            with open(LONG_TERM_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"--> Memory Load Error: {e}")
            return {"preferences": {}, "projects": {}, "aliases": {}, "facts": {}}

    def _save(self):
        try:
            with open(LONG_TERM_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=4)
        except Exception as e:
            print(f"--> Memory Save Error: {e}")

    def add(self, category, key, value):
        with self._lock:
            if category not in self._data:
                self._data[category] = {}
            self._data[category][key] = value
            self._save()

    def delete(self, category, key):
        with self._lock:
            if category in self._data and key in self._data[category]:
                del self._data[category][key]
                self._save()
                return True
            return False

    def get_all(self):
        with self._lock:
            return dict(self._data)

# ─────────────────────────────────────────────────────────────────────────────
# SHORT-TERM MEMORY (Volatile List)
# ─────────────────────────────────────────────────────────────────────────────
class ShortTermMemory:
    def __init__(self):
        self._lock = threading.Lock()
        self._history = []  # list of dicts: [{'user': '...', 'jarvis': '...'}]

    def add_interaction(self, user_text, jarvis_text):
        with self._lock:
            self._history.append({"user": user_text, "jarvis": jarvis_text})
            # Prune to max limit
            if len(self._history) > MAX_SHORT_TERM_CONTEXT:
                self._history.pop(0)

    def get_context_string(self):
        with self._lock:
            if not self._history:
                return ""
            lines = ["\n[RECENT CONVERSATION HISTORY]"]
            for interaction in self._history:
                lines.append(f"User: {interaction['user']}\nJARVIS: {interaction['jarvis']}")
            return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL MEMORY INSTANCES & API
# ─────────────────────────────────────────────────────────────────────────────
_ltm = LongTermMemory()
_stm = ShortTermMemory()

def add_memory(category, key, value):
    """Save persistent fact/preference."""
    if not category: category = "facts"
    _ltm.add(category.lower(), key.lower(), value)

def delete_memory(category, key):
    """Forget persistent fact/preference."""
    if not category: category = "facts"
    return _ltm.delete(category.lower(), key.lower())

def get_long_term_context():
    """Returns a string summary of long term memory for prompt injection."""
    data = _ltm.get_all()
    if not any(data.values()):
        return ""
    
    lines = ["\n[LONG-TERM MEMORY ABOUT THE USER]"]
    for cat, items in data.items():
        if items:
            lines.append(f"- {cat.upper()}:")
            for k, v in items.items():
                lines.append(f"  * {k}: {v}")
    return "\n".join(lines)

def add_chat_context(user_text, jarvis_text):
    """Add a turn to the short-term volatile memory."""
    if user_text and jarvis_text:
        _stm.add_interaction(user_text, jarvis_text)

def get_short_term_context():
    """Returns a string of the recent chat flow."""
    return _stm.get_context_string()

def get_full_context_injection():
    """Combines LTM and STM into a single block to append to the system prompt."""
    ltm = get_long_term_context()
    stm = get_short_term_context()
    
    combined = []
    if ltm: combined.append(ltm)
    if stm: combined.append(stm)
    
    return "\n".join(combined) if combined else ""
