# pydantic_models.py

from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# --- 履歷相關 ---
class ResumeUploadResponse(BaseModel):
    session_id: str
    job_title: str
    summary: str
    structured_data: Dict[str, Any]  # 傳給 Unity 做 UI 顯示用

# --- 面試互動相關 ---
class AnswerRequest(BaseModel):
    session_id: str
    answer_text: str  # Unity 語音轉文字後的內容

class QuestionResponse(BaseModel):
    question_text: str
    audio_url: str    # Unity 播放音檔的網址 (例如 /static/audio/xxx.mp3)
    is_end: bool = False
    