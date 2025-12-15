# pydantic_models.py

from pydantic import BaseModel
from typing import Dict, Any, Optional

# --- 履歷上傳回應 ---
class ResumeUploadResponse(BaseModel):
    session_id: str
    job_title: str
    summary: str
    structured_data: Dict[str, Any]

# --- 面試回應 (修改：移除 audio_url) ---
class QuestionResponse(BaseModel):
    question_text: str  # Unity 收到這個字串後，自己去 call 本地的 TTS
    is_end: bool = False
