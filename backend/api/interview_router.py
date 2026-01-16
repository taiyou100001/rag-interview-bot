# backend/api/interview_router.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from backend.services.session_service import create_session, get_session, update_session
from backend.services.enhanced_agent_service import agent_factory
from backend.services.speech_service import speech_service
from backend.services.feedback_service import feedback_service
from backend.services.rag_service import rag_service
from backend.models.pydantic_models import InterviewStartRequest, InterviewAction
import uuid
import os
from datetime import datetime

router = APIRouter()

@router.post("/start_interview")
async def start_interview(req: InterviewStartRequest):
    """開始面試"""
    try:
        # 驗證並轉換 user_id
        user_id_str = req.user_id
        
        # 如果提供了 resume_id，也轉為字串
        resume_id_str = None
        if req.resume_id:
            resume_id_str = req.resume_id
        
        # 建立 session (直接用字串)
        session = create_session(
            user_id=user_id_str,
            job_title=req.job_title,
            resume_id=resume_id_str,
            resume_text=req.resume_text or ""
        )
        
        # 選擇面試官個性
        personality = req.personality if hasattr(req, 'personality') else 'friendly'
        agent = agent_factory.get_agent(req.job_title, personality=personality)
        
        # 生成第一題
        question = agent.generate_first_question(req.job_title, req.resume_text or "")
        
        # 更新 session
        session.current_question = question
        session.question_count = 1
        update_session(session)
        
        # 生成語音
        audio_filename = f"q_{session.id}_0.mp3"
        audio_path = os.path.join("static/audio", audio_filename)
        os.makedirs("static/audio", exist_ok=True)
        
        try:
            speech_service.text_to_speech(question, audio_path)
        except Exception as e:
            print(f"[TTS] 警告: 語音生成失敗 - {e}")
            # 不中斷流程，只是沒有音檔
        
        return {
            "session_id": str(session.id),
            "question": question,
            "audio_url": f"/audio/{audio_filename}",
            "question_number": 1,
            "total_questions": 10,
            "personality": personality
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"面試啟動失敗: {str(e)}")


@router.post("/process_answer")
async def process_answer(
    session_id: str = Form(...),
    audio: UploadFile = File(...)
):
    """處理求職者回答"""
    try:
        # 取得 session (用字串)
        session = get_session(session_id)
        if not session:
            raise HTTPException(404, "Session not found")

        # 儲存語音檔
        audio_filename = f"answer_{session_id}_{uuid.uuid4()}.wav"
        audio_path = os.path.join("uploads", audio_filename)
        os.makedirs("uploads", exist_ok=True)
        
        with open(audio_path, "wb") as f:
            f.write(await audio.read())

        # STT 轉文字
        user_answer = speech_service.speech_to_text(audio_path)
        
        if not user_answer:
            return {
                "question": "抱歉，我沒有聽清楚您的回答，可以再說一次嗎？",
                "audio_url": "",
                "is_chitchat": True,
                "end": False
            }

        # 更新對話歷史
        if session.history is None:
            session.history = []
        
        session.history.append({
            "question": session.current_question,
            "answer": user_answer,
            "timestamp": datetime.utcnow().isoformat()
        })
        session.question_count += 1
        update_session(session)

        # RAG 檢索
        rag_context = ""
        if session.resume_text:
            retrieved = rag_service.retrieve(f"{session.job_title} {user_answer}", top_k=2)
            if retrieved:
                rag_context = " ".join([r.get('position', '') for r in retrieved])

        # 生成下一題
        agent = agent_factory.get_agent(session.job_title)
        next_question = agent.generate_question(
            job_title=session.job_title,
            resume_text=session.resume_text or "",
            history=session.history,
            context=rag_context
        )

        # 判斷是否結束
        if not next_question or session.question_count >= 10:
            return {
                "end": True,
                "message": "面試已完成，正在生成回饋報告...",
                "question_count": session.question_count
            }

        # 更新 session
        session.current_question = next_question
        update_session(session)

        # 生成 TTS
        audio_filename = f"q_{session.id}_{session.question_count}.mp3"
        audio_path = os.path.join("static/audio", audio_filename)
        
        try:
            speech_service.text_to_speech(next_question, audio_path)
        except Exception as e:
            print(f"[TTS] 警告: {e}")

        # 判斷是否為閒聊
        is_chitchat = any(keyword in next_question for keyword in ["最近", "興趣", "喜歡", "壓力", "休息"])

        return {
            "question": next_question,
            "audio_url": f"/audio/{audio_filename}",
            "question_number": session.question_count,
            "is_chitchat": is_chitchat,
            "end": False
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"處理回答失敗: {str(e)}")


@router.post("/interview_action")
async def interview_action(action_req: InterviewAction):
    """處理面試動作 (下一題/退出)"""
    try:
        session = get_session(action_req.session_id)
        if not session:
            raise HTTPException(404, "Session not found")

        if action_req.action == "exit":
            session.ended_at = datetime.utcnow()
            update_session(session)
            
            return {
                "status": "exited",
                "message": "面試已退出",
                "question_count": session.question_count
            }

        elif action_req.action == "next":
            # 跳過當前題
            if session.history is None:
                session.history = []
            
            session.history.append({
                "question": session.current_question,
                "answer": "[已跳過]",
                "timestamp": datetime.utcnow().isoformat()
            })
            session.question_count += 1
            update_session(session)
            
            # 生成下一題
            agent = agent_factory.get_agent(session.job_title)
            next_question = agent.generate_question(
                job_title=session.job_title,
                resume_text=session.resume_text or "",
                history=session.history
            )
            
            if not next_question:
                return {"end": True, "message": "無更多題目"}
            
            session.current_question = next_question
            update_session(session)
            
            # TTS
            audio_filename = f"q_{session.id}_{session.question_count}.mp3"
            audio_path = os.path.join("static/audio", audio_filename)
            
            try:
                speech_service.text_to_speech(next_question, audio_path)
            except Exception as e:
                print(f"[TTS] 警告: {e}")
            
            return {
                "question": next_question,
                "audio_url": f"/audio/{audio_filename}",
                "question_number": session.question_count
            }
        
        else:
            raise HTTPException(400, f"未知動作: {action_req.action}")

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"動作執行失敗: {str(e)}")


@router.get("/feedback/{session_id}")
async def get_feedback(session_id: str):
    """取得面試回饋報告"""
    try:
        session = get_session(session_id)
        if not session:
            raise HTTPException(404, "Session not found")
        
        # 生成回饋
        feedback = feedback_service.analyze_interview(
            job_title=session.job_title,
            history=session.history or [],
            resume_text=session.resume_text or ""
        )
        
        # 儲存回饋
        session.feedback = {
            "overall_score": feedback.overall_score,
            "dimensions": feedback.dimensions,
            "summary": feedback.summary
        }
        session.ended_at = datetime.utcnow()
        update_session(session)
        
        return {
            "overall_score": feedback.overall_score,
            "dimensions": feedback.dimensions,
            "strengths": feedback.strengths,
            "improvements": feedback.improvements,
            "summary": feedback.summary,
            "interview_data": {
                "job_title": session.job_title,
                "question_count": session.question_count,
                "duration": str(session.ended_at - session.started_at) if session.ended_at else "N/A"
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"回饋生成失敗: {str(e)}")