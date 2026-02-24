"""
API 路由模組
集中匯出所有 API 路由
"""

from backend.api.resume_router import router as resume_router
from backend.api.interview_router import router as interview_router

__all__ = ["resume_router", "interview_router"]
