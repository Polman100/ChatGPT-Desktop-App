from pathlib import Path
import os

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
HISTORY_DIR = BASE_DIR / "Conversation history"

KEY_FILE = BASE_DIR / "key.env"

TITLE_MODEL = "gpt-4o-mini"

AVAILABLE_MODELS = [
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.2",
    "gpt-5.1",
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-3.5-turbo",
    "gpt-4.1",
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.5-preview",
]


def load_api_key() -> str:
    load_dotenv(KEY_FILE)

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError(
            "Brak klucza API. Sprawdź plik key.env!"
        )

    return api_key


def ensure_directories() -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)