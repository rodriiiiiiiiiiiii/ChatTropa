import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEYS = [os.getenv(f"GEMINI_API_KEY_{i}") for i in range(1, 9)]
GEMINI_API_KEYS = [k for k in GEMINI_API_KEYS if k]

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets', 
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/gmail.modify'
]

if not GEMINI_API_KEYS:
    exit(1)