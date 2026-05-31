import automation as auto_lib
import os
from brain import brain
import datetime
import random
import memory
from vision import vision
from automation_controller import automation
import threading
import time
import json

PENDING_ACTION = None
RISKY_ACTIONS = ["delete", "erase_file", "system_control", "send_message"]

# Common Urdu/Hinglish keywords used to detect language
URDU_KEYWORDS = [
    "kya", "kar", "karo", "chala", "chalao", "kholo", "bata", "batao",
    "ha", "hai", "hain", "ho", "waqt", "abhi", "mera", "mujhe", "aap",
    "sun", "yaar", "bhai", "sir", "jarvis", "band", "khol", "dhoondo",
    "woh", "kuch", "thoda", "zyada", "pehle", "baad", "kab", "kaise",
    "kyun", "main", "tum", "hum", "kal", "aaj", "kal", "nahi", "haan"
]

def is_urdu(text):
    """Returns True if the text appears to be Urdu/Hinglish."""
    words = text.lower().split()
    return any(w in URDU_KEYWORDS for w in words)

def process_command(text):
    text_clean = text.lower().strip()
    urdu = is_urdu(text_clean)

    # 0. CHECK FOR PENDING CONFIRMATIONS
    confirmation_response = confirm_pending_action(text_clean, urdu)
    if confirmation_response:
        return confirmation_response, "CONFIRMATION"

    # 1. DIRECT COMMANDS
    greetings = ["hello", "hi", "hey", "jarvis", "wake up"]
    if any(greet == text_clean for greet in greetings):
        return "Ji Boss, batayein main kya kar sakta hu?" if urdu else "At your service, Sir. How can I help?", "GREETING"

    # Emergency Stop
    if text_clean in ["stop", "abort", "ruk jao", "bas", "khamosh"]:
        automation.abort()
        return "Ji Sir, ruk gaya." if urdu else "Automation aborted, Sir.", "STOP"

    # Time/Date
    if "time" in text_clean or "waqt" in text_clean:
        now = datetime.datetime.now().strftime("%H:%M")
        return (f"Abhi waqt ha {now}, Sir." if urdu else f"The time is {now}, Sir."), None

    # YouTube Specific
    if "youtube pe" in text_clean or "youtube per" in text_clean or "youtube par" in text_clean:
        song = text_clean.replace("youtube pe", "").replace("youtube per", "").replace("youtube par", "").replace("khol", "").replace("chala", "").strip()
        if song:
            auto_lib.open_youtube(song)
            return (f"Ji Sir, abhi {song} YouTube par chala deta hu." if urdu else f"Playing {song} on YouTube, Sir."), "ACTION"

    # 2. VISION COMMANDS
    vision_triggers = [
        "what's on my screen", "what am i doing", "what am i working on", 
        "summarize this page", "summarize this", "explain this",
        "screen pe kya chal raha", "is page ko explain karo", "see my screen",
        "look at my screen", "what is this", "what is on my screen",
        "isey dekho", "dekho screen par", "what's this", "identify this",
        "click on", "type in", "type this", "scroll down", "scroll up",
        "click karo", "type karo", "upar scroll karo", "neeche scroll karo"
    ]
    if any(trigger in text_clean for trigger in vision_triggers):
        active_title, img = vision.get_current_context()
        if img:
            ai_response, action_data = brain.get_response(text, image=img)
            if action_data:
                result_msg = execute_ai_action(action_data, urdu)
                final_text = f"{ai_response} {result_msg}".strip()
                memory.add_chat_context(text, final_text)
                return final_text, "VISION"
            
            memory.add_chat_context(text, ai_response)
            return ai_response, "VISION"
        else:
            return "Main abhi screen nahi dekh pa raha hu, Sir." if urdu else "I am unable to see the screen right now, Sir.", "ERROR"

    # 3. AI REASONING FALLBACK (Flexible Intent Second)
    ai_response, action_data = brain.get_response(text)

    if action_data:
        result_msg = execute_ai_action(action_data, urdu)
        final_text = f"{ai_response} {result_msg}".strip()
        memory.add_chat_context(text, final_text)
        return final_text, "AI_ACTION"

    memory.add_chat_context(text, ai_response)
    return ai_response, "AI"

def execute_ai_action(data, urdu=False):
    """Safely dispatches AI-suggested actions to automation functions."""
    global PENDING_ACTION
    action = data.get("action")
    target = data.get("target", "")

    # Safety Check: If this is a risky action and not yet confirmed
    if action in RISKY_ACTIONS and PENDING_ACTION is None:
        PENDING_ACTION = data
        if urdu:
            return f"Sir, kya aap waqai {action} karna chahte hain? Confirm kijiye."
        return f"Sir, are you sure you want to proceed with {action}? Please confirm."

    try:
        if action == "open_app":
            if auto_lib.open_app(target): # Original helper
                # Wait for the window to appear before confirming success
                threading.Thread(target=automation.wait_for_window, args=(target, 8), daemon=True).start()
                return f"{target} khol raha hu, Sir." if urdu else f"Opening {target}, Sir."

        elif action == "open_folder":
            folders = {
                "downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
                "documents": os.path.join(os.path.expanduser("~"), "Documents"),
                "desktop": os.path.join(os.path.expanduser("~"), "Desktop")
            }
            path = folders.get(target.lower(), target)
            if auto_lib.open_folder(path):
                return f"Aapka {target} folder open kar raha hu." if urdu else f"Opening your {target} folder."

        elif action == "open_website":
            url = target if "://" in target else f"https://{target}"
            import webbrowser
            webbrowser.open(url)
            return f"{target} khul raha ha, Sir." if urdu else f"Opening {target} in your browser."

        elif action == "search_google":
            auto_lib.open_google(target)
            return f"Google par {target} dhoond raha hu." if urdu else f"Searching Google for {target}."

        elif action == "play_youtube":
            auto_lib.open_youtube(target)
            return f"YouTube par {target} play kar raha hu." if urdu else f"Playing {target} on YouTube."

        elif action == "system_control":
            print(f"--> [DEBUG] System Control Target: {target}")
            if target == "volume_up":
                auto_lib.set_volume(80)
                return "Volume barha di ha." if urdu else "Volume turned up."
            if target == "volume_down":
                auto_lib.set_volume(20)
                return "Volume kam kar di ha." if urdu else "Volume turned down."
            if target in ["screenshot", "take_screenshot", "capture"]:
                result = auto_lib.take_screenshot()
                if result:
                    return "Screenshot le liya ha." if urdu else "Screenshot taken."
                else:
                    return "Maafi chahta hu, screenshot nahi le saka." if urdu else "Sorry, I couldn't capture the screenshot."

        elif action == "search_file":
            os.system(f"start explorer shell:AppsFolder\\search-ms:query={target}")
            return f"System mein {target} dhoond raha hu." if urdu else f"Searching for {target} on your system."

        # ── File System Actions ───────────────────────────────────────────
        elif action == "create_folder":
            path = data.get("path", "Desktop/new_folder")
            result = auto_lib.create_folder(path)
            name = os.path.basename(result) if result else path
            return f"Folder '{name}' bana diya, Sir." if urdu else f"Folder '{name}' created."

        elif action == "create_file":
            path = data.get("path", "Desktop/new_file.txt")
            result = auto_lib.create_file(path)
            name = os.path.basename(result) if result else path
            return f"File '{name}' bana di, Sir." if urdu else f"File '{name}' created."

        elif action == "write_file":
            path    = data.get("path", "")
            content = data.get("content", "")
            result  = auto_lib.write_file(path, content)
            name = os.path.basename(result) if result else path
            return f"'{name}' mein likh diya, Sir." if urdu else f"Written to '{name}'."

        elif action == "append_file":
            path    = data.get("path", "")
            content = data.get("content", "")
            result  = auto_lib.append_file(path, content)
            name = os.path.basename(result) if result else path
            return f"'{name}' mein add kar diya." if urdu else f"Appended to '{name}'."

        elif action == "erase_file":
            path   = data.get("path", "")
            result = auto_lib.erase_file(path)
            name   = os.path.basename(result) if result else path
            if result:
                return f"'{name}' ka content erase kar diya." if urdu else f"'{name}' content cleared."
            return "File nahi mili, Sir." if urdu else "File not found."

        elif action == "delete":
            path   = data.get("path", "")
            result = auto_lib.delete_path(path)
            if result == "blocked":
                return "Ye protected path ha, delete nahi kar sakta." if urdu else "That path is protected. Deletion blocked."
            if result == "not_found":
                return "File ya folder nahi mila, Sir." if urdu else "File or folder not found."
            if not result:
                return "File shayad open ha ya permission nahi ha. Try close it first." if urdu else "Deletion failed. File might be in use or require admin rights."
            name = os.path.basename(result) if result else path
            return f"'{name}' delete kar diya." if urdu else f"'{name}' deleted."

        elif action == "move":
            src    = data.get("source", "")
            dest   = data.get("destination", "")
            result = auto_lib.move_path(src, dest)
            if result == "not_found":
                return "Source file nahi mili, Sir." if urdu else "Source not found."
            name = os.path.basename(result) if result else dest
            return f"Move kar diya, Sir." if urdu else f"Moved to '{name}'."

        # ── Memory Actions ────────────────────────────────────────────────
        elif action == "remember":
            category = data.get("category", "facts")
            key      = data.get("key", "")
            value    = data.get("value", "")
            if key and value:
                memory.add_memory(category, key, value)
                return f"'{key}' yaad rakhunga, Sir." if urdu else f"I've committed '{key}' to memory."
            return ""

        elif action == "forget":
            category = data.get("category", "facts")
            key      = data.get("key", "")
            if memory.delete_memory(category, key):
                return f"'{key}' bhula diya." if urdu else f"I've erased '{key}' from memory."
            return "Mujhe ye yaad nahi tha." if urdu else "I didn't have that in my memory."

        elif action == "view_memory":
            import json
            ltm = memory._ltm.get_all()
            print(f"--> JARVIS MEMORY DUMP:\n{json.dumps(ltm, indent=2)}")
            return "Screen par meri memory display kar di hai, Sir." if urdu else "I've displayed my memory banks in the console."
        
        # ── Computer Operator Actions ─────────────────────────────────────
        elif action == "click_at":
            x_pct = data.get("x_pct", 50)
            y_pct = data.get("y_pct", 50)
            clicks = data.get("clicks", 1)
            button = data.get("button", "left")
            x, y = vision.map_coordinates(x_pct, y_pct)
            
            # Start in a separate thread to not block the main command flow
            threading.Thread(target=automation.click, args=(x, y, button, clicks), daemon=True).start()
            return f"{x_pct} percent coordinates par click kar raha hu." if urdu else f"Clicking at {x_pct}%, {y_pct}%."

        elif action == "type_into":
            text_to_type = data.get("text", "")
            target_win   = data.get("target_window", "")
            submit       = data.get("submit", False)
            
            def _type_task():
                # 1. Focus the window if specified
                if target_win:
                    if not automation.wait_for_window(target_win, timeout=3):
                        print(f"--> [DEBUG] Window '{target_win}' not found. Attempting to open it.")
                        auto_lib.open_app(target_win)
                        if not automation.wait_for_window(target_win, timeout=8):
                            print(f"--> [ERROR] Could not open or find window '{target_win}'.")
                            return
                
                # 2. Ensure focus inside the window
                automation.ensure_ready_for_typing()
                
                # 3. Type
                automation.type_text(text_to_type)
                
                # 4. Submit
                if submit:
                    time.sleep(0.5)
                    automation.press_key("enter")
                
                print(f"--> Automation: [COMPLETED] Typed text into '{automation.get_active_window_title()}'")
            
            threading.Thread(target=_type_task, daemon=True).start()
            return f"Type kar raha hu: {text_to_type}" if urdu else f"Typing text into window, Sir."

        elif action == "press_key":
            key = data.get("key", "enter")
            automation.press_key(key)
            return f"{key} press kar diya." if urdu else f"Pressed {key}."

        elif action == "press_hotkey":
            keys = data.get("keys", [])
            automation.hotkey(*keys)
            return f"Hotkey {keys} execute kar di." if urdu else f"Executed hotkey {keys}."

        elif action == "scroll_screen":
            amount = data.get("amount", -300)
            automation.scroll(amount)
            return "Scroll kar raha hu." if urdu else "Scrolling screen."

        elif action == "wait":
            duration = data.get("duration", 1.0)
            time.sleep(duration)
            return ""

    except Exception as e:
        print(f"Tool Execution Error: {e}")

    return ""

def confirm_pending_action(text_clean, urdu=False):
    """Checks if the user is confirming or denying a pending sensitive action."""
    global PENDING_ACTION
    if not PENDING_ACTION:
        return None

    yes_words = ["yes", "haan", "ji", "theek ha", "kar do", "proceed", "okay", "ok"]
    no_words = ["no", "nahi", "rehne do", "cancel", "stop", "mat karo"]

    if any(w in text_clean for w in yes_words):
        action_data = PENDING_ACTION
        PENDING_ACTION = None
        return execute_ai_action(action_data, urdu)
    
    if any(w in text_clean for w in no_words):
        PENDING_ACTION = None
        return "Theek ha Sir, cancel kar diya." if urdu else "Understood, Sir. Action cancelled."

    return None
