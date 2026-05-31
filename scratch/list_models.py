import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from google import genai
from config import GEMINI_API_KEY

def list_models():
    client = genai.Client(api_key=GEMINI_API_KEY)
    print("Listing models...")
    try:
        for model in client.models.list():
            print(f"Model Name: {model.name}")
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    list_models()
