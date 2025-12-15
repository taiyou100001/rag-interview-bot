# backend/api/__init__.py
from .resume_router import router as resume_router
from .interview_router import router as interview_router
from .audio_router import router as audio_router

__all__ = ["resume_router", "interview_router", "audio_router"]