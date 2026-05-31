import json
import re
import requests
from google import genai
from config import GEMINI_API_KEY, GROQ_API_KEY, SYSTEM_PROMPT
import memory
from vision import vision

# ---------------------------------------------------------------------------
# Response trimmer — keeps spoken text short for faster TTS synthesis.
# Strips markdown, trims to first 2 sentences, collapses whitespace.
# ---------------------------------------------------------------------------
_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')

def _trim_response(text: str) -> str:
    """Clean and shorten AI response text before it reaches TTS."""
    text = re.sub(r'```json[\s\S]*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'```[\s\S]*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'`[^`]*`', '', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'[-•]\s+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    sentences = _SENTENCE_SPLIT.split(text)
    return ' '.join(sentences[:2]).strip()

# ---------------------------------------------------------------------------
# Language detector — used to inject a per-request language hint into the AI.
# Scoring-based: counts Urdu keywords vs total words to avoid false positives.
# ---------------------------------------------------------------------------
_URDU_WORDS = {
    'kya', 'kar', 'karo', 'chala', 'chalao', 'kholo', 'bata', 'batao',
    'ha', 'hai', 'hain', 'ho', 'waqt', 'abhi', 'mera', 'mujhe', 'aap',
    'sun', 'yaar', 'bhai', 'band', 'khol', 'dhoondo', 'woh', 'kuch',
    'thoda', 'zyada', 'pehle', 'baad', 'kab', 'kaise', 'kyun', 'main',
    'tum', 'hum', 'aaj', 'kal', 'nahi', 'haan', 'bilkul', 'theek',
    'suno', 'batao', 'dedo', 'lao', 'jao', 'ruk', 'chalo', 'mere',
    'tumhara', 'mujhko', 'please', 'yeh', 'woh', 'uska', 'mera', 'tera'
}

def detect_language(text: str) -> str:
    """
    Returns 'urdu' if the text is primarily Urdu/Hinglish, else 'english'.
    Uses a keyword score: if >25% of words are Urdu keywords, classify as Urdu.
    """
    words = text.lower().split()
    if not words:
        return 'english'
    urdu_count = sum(1 for w in words if w in _URDU_WORDS)
    ratio = urdu_count / len(words)
    return 'urdu' if ratio >= 0.25 else 'english'

def _tagged_input(user_input: str) -> str:
    """
    Prepends a hard language instruction and any dynamic memory context
    to the user input, keeping the system prompt static.
    """
    lang = detect_language(user_input)
    tag = '[RESPOND IN ROMAN URDU/HINGLISH ONLY]' if lang == 'urdu' else '[RESPOND IN ENGLISH ONLY]'
    
    # Inject memory context dynamically
    memory_context = memory.get_full_context_injection()
    
    # Inject active window context
    active_window = vision.get_active_window()
    vision_context = f"[ACTIVE WINDOW: {active_window}]"
    
    return f"{vision_context}\n{memory_context}\n\n{tag}\nUser: {user_input}".strip()

# Modern System Instruction
AI_INSTRUCTION = SYSTEM_PROMPT + """
RESPONSE FORMATTING:
- Every response must follow the CONVERSATIONAL RULES.
- If an action is required, append the following JSON block:
```json
{
  "action": "ACTION_NAME",
  "target": "TARGET_VALUE"
}
```
STANDARD ACTIONS: open_app, open_folder, open_website, search_google, play_youtube, system_control, search_file.
- Example Screenshot: {"action": "system_control", "target": "screenshot"}

COMPUTER OPERATOR ACTIONS — for direct desktop interaction:
- Click at:     {"action": "click_at", "x_pct": 50, "y_pct": 50, "clicks": 1, "button": "left"}
- Type text:    {"action": "type_into", "text": "hello world", "target_window": "Notepad", "submit": true}
- Press key:    {"action": "press_key", "key": "enter"}
- Press hotkey: {"action": "press_hotkey", "keys": ["ctrl", "c"]}
- Scroll:       {"action": "scroll_screen", "amount": -500}
- Wait:         {"action": "wait", "duration": 1.5}

DESKTOP INTERACTION RULES:
1. ALWAYS specify 'target_window' in 'type_into' if you just opened an app.
2. If you need to open a file AND type in it, first use 'open_app' or 'write_file', then 'type_into'.
3. Wait for 1-2 seconds ('wait' action) after opening a new app before typing.
4. Coordinates are 0-100 (percentage of screen).

COORDINATE SYSTEM:
- Use percentage-based coordinates (x_pct, y_pct) from 0 to 100.
- (0,0) is top-left, (100,100) is bottom-right.
- If you see a button in a screenshot, estimate its center % coordinates.

FILE SYSTEM ACTIONS — use exactly these JSON schemas:
- Create folder:  {"action": "create_folder", "path": "Downloads/my_folder"}
- Create file:    {"action": "create_file",   "path": "Desktop/notes.txt"}
- Write file:     {"action": "write_file",    "path": "Desktop/notes.txt", "content": "hello world"}
- Append file:    {"action": "append_file",   "path": "Desktop/notes.txt", "content": "extra line"}
- Erase file:     {"action": "erase_file",    "path": "Desktop/notes.txt"}
- Delete path:    {"action": "delete",        "path": "Downloads/old.txt"}
- Move path:      {"action": "move",          "source": "Desktop/a.txt", "destination": "Downloads/a.txt"}

MEMORY ACTIONS — use these to manage long-term memory:
- Remember fact:  {"action": "remember", "category": "preferences", "key": "theme", "value": "dark"}
- Forget fact:    {"action": "forget",   "category": "preferences", "key": "theme"}
- View memory:    {"action": "view_memory"}

VISUAL CAPABILITIES:
- You have access to the user's screen when they ask about it.
- If an image is provided, analyze it to answer the user's specific query about their screen.
- You are ALWAYS provided with the [ACTIVE WINDOW: title] context. Use this to sound more aware.
- Example: If the active window is 'Visual Studio Code', you can say 'I see you are coding, sir.'

PATH RULES:
- Translate locations to prefixes like: "Desktop", "Downloads", "Documents", "Music", "Videos", "Pictures".
- If no extension is specified, default to .txt.
- If no location is given, default to Desktop.
"""

class JarvisBrain:
    def __init__(self):
        print("--> JARVIS: Initializing Modern Dual-Neural Link...")
        # Configure Gemini (New SDK)
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model_id = 'gemini-2.0-flash'
        
        self.chat = self.client.chats.create(
            model=self.model_id,
            config={'system_instruction': AI_INSTRUCTION}
        )
        
        # Configure Groq Fallback
        self.groq_key = GROQ_API_KEY
        self.groq_url = "https://api.groq.com/openai/v1/chat/completions"

    def get_response(self, user_input, image=None):
        # Tag the input with a language hint so the model can't drift
        tagged = _tagged_input(user_input)
        lang = detect_language(user_input)

        # Attempt 1: Gemini (New SDK)
        try:
            if image:
                response = self.chat.send_message([image, tagged])
            else:
                response = self.chat.send_message(tagged)
            return self._process_raw_response(response.text)
        except Exception as e:
            print(f"--> Gemini Neural Path Error: {e}. Switching to Groq...")

        # Attempt 2: Groq (High-Speed Fallback)
        try:
            return self._get_groq_response(tagged)
        except Exception as e:
            print(f"--> Groq Path Blocked: {e}")
            if lang == 'urdu':
                return "Maafi chahta hu sir, network me kuch masla aa raha ha.", None
            return "Sorry sir, I'm having trouble reaching my neural network.", None

    def _get_groq_response(self, tagged_input):
        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": AI_INSTRUCTION},
                {"role": "user", "content": tagged_input}
            ],
            "temperature": 0.5,
            "max_tokens": 120,
        }
        response = requests.post(self.groq_url, headers=headers, json=data)
        if response.status_code == 200:
            text = response.json()['choices'][0]['message']['content']
            return self._process_raw_response(text)
        raise Exception(f"Groq API Error: {response.text}")

    def _process_raw_response(self, text):
        action_data = self._extract_action(text)
        # Always trim — removes JSON block + markdown + caps length for TTS speed
        clean_text = _trim_response(text)
        return clean_text, action_data

    def _extract_action(self, text):
        try:
            match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
        except:
            pass
        return None

# Global instance
brain = JarvisBrain()
