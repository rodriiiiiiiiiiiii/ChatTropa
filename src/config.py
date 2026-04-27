import os
from dotenv import load_dotenv

load_dotenv()

# IA & APIs
GEMINI_API_KEYS = [os.getenv(f"GEMINI_API_KEY_{i}") for i in range(1, 9)]
GEMINI_API_KEYS = [k for k in GEMINI_API_KEYS if k]

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Google Scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.modify",
]

# --- FILTRO ANTI-SPAM ---
BLACKLIST_SUBJECTS = [
    "almacenamiento de gmail",
    "delivery status notification",
    "bienvenida a la aplicación google one",
    "alerta de seguridad",
    "nuevo inicio de sesión",
    "notificación de estado de entrega",
]

BLACKLIST_SENDERS = [
    "no-reply@google.com",
    "mail-noreply@google.com",
    "google-noreply@google.com",
]
