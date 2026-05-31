import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from google import genai
from config import GEMINI_API_KEY

def test_gemini():
    client = genai.Client(api_key=GEMINI_API_KEY)
    model_id = 'gemini-3-flash-preview' # Or 'models/gemini-3-flash-preview'
    print(f"Testing model: {model_id}")
    try:
        response = client.models.generate_content(
            model=model_id,
            contents="Hello, are you there?"
        )
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_gemini()
