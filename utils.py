# utils.py
from langdetect import detect
from dotenv import load_dotenv
from pathlib import Path
import os

def detect_language(text):
    try:
        lang = detect(text)
        return "zh" if lang.startswith("zh") else "en"
    except Exception:
        return "unknown"

def clean_text(text):
    return text.strip().replace("\n", " ")

def get_hf_token():
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / "bin" / ".env")
    token = os.environ.get("TOKEN")
    if not token:
        raise ValueError("❌ 找不到 HuggingFace TOKEN，請檢查 .env 檔案。")
    return token
