# JARVIS AI Assistant

A fully functional Iron Man-inspired desktop assistant built with Python, PyQt5, and Google Gemini AI.

## Features
- **Iron Man HUD GUI**: Glowing cyan interface with pulsing animations and real-time waveform.
- **Voice Interaction**: Listen for commands and respond in a professional JARVIS-style voice.
- **AI Brain**: Powered by Google Gemini for intelligent, witty, and concise conversations.
- **Automation**: Open YouTube, search Google, take screenshots, control volume, launch apps, and check weather.
- **Chat History**: Visual conversation log with timestamps.

## Setup Instructions

### 1. Install Python
Make sure you have Python 3.8+ installed on your system.

### 2. Install Dependencies
Open your terminal/command prompt in this folder and run:
```bash
pip install -r requirements.txt
```

### 3. Configure API Keys

This project requires API keys for AI functionality.

Open `config.py` and add your keys:

```python
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
GROQ_API_KEY = "YOUR_GROQ_API_KEY"
```

Get your API keys here:

* Gemini API: https://aistudio.google.com/app/apikey
* Groq API: https://console.groq.com/keys


### 4. Run JARVIS
To start the system, run:
```bash
python jarvis.py
```

## How to Use
- **Mic Button**: Click the glowing mic button at the bottom center to start listening.
- **Commands**: 
  - "Play Believer on YouTube"
  - "Search for latest space news"
  - "Take a screenshot"
  - "Open Notepad"
  - "What is the weather in New York?"
  - "Who are you?"

## Troubleshooting
- **Mic not working**: Ensure your default microphone is set correctly in Windows settings.
- **No Voice**: `pyttsx3` uses system voices. Ensure you have English voices installed in Windows "Speech" settings.
- **Internet**: An active internet connection is required for AI responses and web automation.

---
*Created by JARVIS Initialization Protocol*
