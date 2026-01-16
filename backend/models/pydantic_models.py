# backend/models/pydantic_models.py
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

class InterviewStartRequest(BaseModel):
    """開始面試請求"""
    user_id: str
    job_title: str
    resume_id: Optional[str] = None
    resume_text: Optional[str] = None
    personality: Optional[str] = "friendly"  # ✅ 新增: 面試官個性

class InterviewAction(BaseModel):
    """面試動作請求 (下一題/退出)"""
    session_id: str
    action: str  # "next" 或 "exit"
