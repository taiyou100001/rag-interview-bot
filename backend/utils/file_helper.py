# backend/utils/file_helper.py
import os
import uuid
import shutil
from datetime import datetime
from backend.config import settings

def ensure_dirs():
    """專案啟動時自動建立必要資料夾"""
    os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(settings.AUDIO_FOLDER, exist_ok=True)

def save_upload_file(upload_file, subfolder: str = "") -> str:
    """
    安全儲存上傳檔案，回傳相對路徑
    範例：uploads/resume/20250405_abc123.pdf
    """
    today = datetime.now().strftime("%Y%m%d")
    folder = os.path.join(settings.UPLOAD_FOLDER, subfolder, today)
    os.makedirs(folder, exist_ok=True)
    
    filename = f"{uuid.uuid4()}_{upload_file.filename}"
    filepath = os.path.join(folder, filename)
    
    with open(filepath, "wb") as f:
        shutil.copyfileobj(upload_file.file, f)
    
    return filepath

def generate_audio_path(session_id: str, question_index: int) -> str:
    """統一產生 TTS 音檔命名規則"""
    filename = f"q_{session_id}_{question_index}.mp3"
    return os.path.join(settings.AUDIO_FOLDER, filename)

def cleanup_old_files(days: int = 7):
    """定期清理舊的上傳與音檔（可搭配 monitor.py 使用）"""
    import time
    now = time.time()
    for folder in [settings.UPLOAD_FOLDER, settings.AUDIO_FOLDER]:
        for root, _, files in os.walk(folder):
            for f in files:
                path = os.path.join(root, f)
                if os.stat(path).st_mtime < now - days * 86400:
                    os.remove(path)