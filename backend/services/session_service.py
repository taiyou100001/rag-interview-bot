# backend/services/session_service.py
from backend.database import SessionLocal, InterviewSession
from uuid import UUID

def create_session(user_id: UUID, job_title: str, resume_id: UUID | None = None, resume_text: str = ""):
    session = InterviewSession(
        user_id=user_id,
        job_title=job_title,
        resume_id=resume_id,
        resume_text=resume_text,
        history=[],
        current_question="",
        question_count=0
    )
    with SessionLocal() as db:
        db.add(session)
        db.commit()
        db.refresh(session)
    return session

def get_session(session_id: UUID):
    with SessionLocal() as db:
        return db.query(InterviewSession).filter(
            InterviewSession.id == session_id
        ).first()

def update_session(session):
    with SessionLocal() as db:
        db.merge(session)
        db.commit()

# 讓 import 更方便
__all__ = ["create_session", "get_session", "update_session"]