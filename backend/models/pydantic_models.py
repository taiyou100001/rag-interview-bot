# backend/models/pydantic_models.py
from pydantic import BaseModel
from typing import Optional

class InterviewStartRequest(BaseModel):
    user_id: str
    job_title: str
    resume_id: Optional[str] = None
    resume_text: Optional[str] = None