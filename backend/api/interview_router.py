# backend/api/interview_router.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from backend.services.session_service import create_session, get_session, update_session
from backend.services.agent_service import agent_factory
from backend.services.speech_service import speech_service
from backend.models.pydantic_models import InterviewStartRequest
import uuid
import os

router = APIRouter()

@router.post("/start_interview")
async def start_interview(req: InterviewStartRequest):
    session = create_session(
        user_id=uuid.UUID(req.user_id),
        job_title=req.job_title,
        resume_id=uuid.UUID(req.resume_id) if req.resume_id else None,
        resume_text=req.resume_text or ""
    )
    
    agent = agent_factory.get_agent(req.job_title)
    question = agent.generate_first_question(req.job_title, req.resume_text or "")
    
    audio_path = f"static/audio/q_{session.id}_0.mp3"
    speech_service.text_to_speech(question, audio_path)
    
    return {
        "session_id": str(session.id),
        "question": question,
        "audio_url": f"/audio/q_{session.id}_0.mp3"
    }

@router.post("/process_answer")
async def process_answer(
    session_id: str = Form(...),
    audio: UploadFile = File(...)
):
    session = get_session(uuid.UUID(session_id))
    if not session:
        raise HTTPException(404, "Session not found")

    # 保存語音
    audio_path = f"uploads/answer_{session_id}_{uuid.uuid4()}.wav"
    with open(audio_path, "wb") as f:
        f.write(await audio.read())

    # STT
    user_answer = speech_service.speech_to_text(audio_path)

    # 更新歷史
    session.history.append({"question": session.current_question, "answer": user_answer})
    update_session(session)

    # 生成下一題
    agent = agent_factory.get_agent(session.job_title)
    next_question = agent.generate_question(session.job_title, session.resume_text, session.history)

    if not next_question:
        return {"end": True, "message": "面試結束"}

    session.current_question = next_question
    update_session(session)

    audio_path = f"static/audio/q_{session.id}_{len(session.history)}.mp3"
    speech_service.text_to_speech(next_question, audio_path)

    return {
        "question": next_question,
        "audio_url": f"/audio/q_{session.id}_{len(session.history)}.mp3"
    }