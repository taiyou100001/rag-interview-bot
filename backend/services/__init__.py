# backend/services/__init__.py
"""
Services 模組：封裝所有業務邏輯服務
"""

# 確保按順序載入，避免循環引用
from .ocr_service import ocr_service
from .resume_service import resume_service
from .rag_service import rag_service
from .enhanced_agent_service import agent_factory
from .feedback_service import feedback_service
from .speech_service import speech_service
from .session_service import create_session, get_session, update_session

__all__ = [
    "ocr_service",
    "resume_service",
    "rag_service",
    "agent_factory",
    "feedback_service",
    "speech_service",
    "create_session",
    "get_session",
    "update_session",
]