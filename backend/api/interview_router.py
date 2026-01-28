# backend/api/interview_router.py
import os
import shutil
import time
import uuid
from typing import Optional
from datetime import datetime
import logging

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from backend.services.session_service import create_session, get_session, update_session
from backend.services.enhanced_agent_service import agent_factory
from backend.services.speech_service import speech_service
from backend.services.feedback_service import feedback_service
from backend.services.rag_service import rag_service
from backend.models.pydantic_models import InterviewStartRequest, InterviewAction
from backend.config import settings  # 假設你有 config 設定檔，若無可直接寫死路徑

# 設定 Log
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# --- Helper Functions ---

def check_voice_command(text: str) -> Optional[str]:
    """
    檢查文字中是否包含下一題或退出的指令
    """
    if not text:
        return None

    # 移除空格與標點符號方便比對
    clean_text = text.replace(" ", "").replace("。", "").replace("！", "").replace("？", "")
    
    # 定義關鍵字清單
    exit_keywords = ["退出", "結束面試", "停止面試", "不面試了", "離開"]
    # 加入可能聽錯的諧音
    next_keywords = ["下一題", "跳過", "換一題", "下一個問題", "下一天", "恰一聽", "摘婷", "車題"] 
    
    for kw in exit_keywords:
        if kw in clean_text:
            return "EXIT"
    
    for kw in next_keywords:
        if kw in clean_text:
            return "NEXT"
    
    return None

def save_audio_file(session_id: str, audio_file: UploadFile) -> str:
    """
    儲存音檔至永久目錄
    Returns: file_path
    """
    # 1. 建立永久儲存目錄
    save_dir = os.path.join("saved_audio") # 或者用 settings.BASE_DIR 拼接
    os.makedirs(save_dir, exist_ok=True)

    # 2. 產生唯一檔名 (包含時間戳記與 UUID 防止覆蓋)
    unique_name = f"{session_id}_{int(time.time())}_{uuid.uuid4().hex[:5]}.wav"
    file_path = os.path.join(save_dir, unique_name)
    
    # 3. 寫入檔案
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
        logger.info(f"💾 音檔已儲存: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"儲存音檔失敗: {e}")
        raise HTTPException(status_code=500, detail="音檔儲存失敗")

# --- Endpoints ---

@router.post("/start_interview")
async def start_interview(req: InterviewStartRequest):
    """開始面試"""
    try:
        user_id_str = req.user_id
        resume_id_str = req.resume_id if req.resume_id else None
        
        session = create_session(
            user_id=user_id_str,
            job_title=req.job_title,
            resume_id=resume_id_str,
            resume_text=req.resume_text or ""
        )
        
        personality = req.personality if hasattr(req, 'personality') else 'friendly'
        agent = agent_factory.get_agent(req.job_title, personality=personality)
        
        # 生成第一題
        question = agent.generate_first_question(req.job_title, req.resume_text or "")
        
        session.current_question = question
        session.question_count = 1
        update_session(session)
        
        # 生成 TTS
        audio_filename = f"q_{session.id}_0.mp3"
        audio_path = os.path.join("static/audio", audio_filename)
        os.makedirs("static/audio", exist_ok=True)
        
        try:
            speech_service.text_to_speech(question, audio_path)
        except Exception as e:
            logger.warning(f"[TTS] 警告: 語音生成失敗 - {e}")
        
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
        session = get_session(session_id)
        if not session:
            raise HTTPException(404, "Session not found")

        # 1. 儲存音檔
        audio_path = save_audio_file(session_id, audio)

        # 2. STT 轉文字
        user_answer = speech_service.speech_to_text(audio_path)
        logger.info(f"🎤 使用者說 ({session_id}): {user_answer}")
        
        if not user_answer:
            return {
                "question": "抱歉，我沒有聽清楚您的回答，可以再說一次嗎？",
                "audio_url": "",
                "is_chitchat": True,
                "end": False
            }

        # 3. 🔥 指令判斷邏輯
        command = check_voice_command(user_answer)

        # --- 分支 A: 退出指令 ---
        if command == "EXIT":
            logger.info("🛑 偵測到語音退出指令")
            session.ended_at = datetime.utcnow()
            update_session(session)
            return {
                "end": True, 
                "message": "收到退出指令，面試結束。",
                "question": "好的，今天的面試到此結束，辛苦了。", # 前端顯示用
                "audio_url": "" # 可選：生成一個結束語音
            }

        # --- 分支 B: 下一題指令 ---
        elif command == "NEXT":
            logger.info("⏭️ 偵測到下一題指令，跳過此題")
            # 記錄跳過
            if session.history is None:
                session.history = []
            
            session.history.append({
                "question": session.current_question,
                "answer": f"（使用者語音要求跳過：{user_answer}）",
                "audio_path": audio_path, # 記錄音檔路徑
                "timestamp": datetime.utcnow().isoformat()
            })
            # 不增加 question_count，或者增加看你的邏輯，這裡假設跳過也算一題
            session.question_count += 1
            
            # 生成下一題 (不使用 RAG，因為沒有有效回答)
            agent = agent_factory.get_agent(session.job_title)
            next_question = agent.generate_question(
                job_title=session.job_title,
                resume_text=session.resume_text or "",
                history=session.history
            )

            print(f"========================================")
            print(f" AI 生成的題目 (跳過後): {next_question}")
            print(f"========================================")

        # --- 分支 C: 正常回答 ---
        else:
            # 更新對話歷史
            if session.history is None:
                session.history = []
            
            session.history.append({
                "question": session.current_question,
                "answer": user_answer,
                "audio_path": audio_path, # 記錄音檔路徑
                "timestamp": datetime.utcnow().isoformat()
            })
            session.question_count += 1

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

            print(f"========================================")
            print(f" AI 生成的題目: {next_question}")
            print(f"========================================")

        # --- 共用後續處理 (更新 Session & TTS) ---
        
        # 判斷是否結束 (題數上限 或 AI 沒題目了)
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
        audio_path_tts = os.path.join("static/audio", audio_filename)
        
        try:
            speech_service.text_to_speech(next_question, audio_path_tts)
        except Exception as e:
            logger.warning(f"[TTS] 警告: {e}")

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
    """處理按鈕動作 (保留此 Endpoint 供前端按鈕使用)"""
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
            if session.history is None:
                session.history = []
            
            session.history.append({
                "question": session.current_question,
                "answer": "[使用者按鈕跳過]",
                "timestamp": datetime.utcnow().isoformat()
            })
            session.question_count += 1
            
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
            except Exception:
                pass
            
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
        raise HTTPException(500, f"動作執行失敗: {str(e)}")


@router.get("/feedback/{session_id}")
async def get_feedback(session_id: str):
    """取得面試回饋報告"""
    try:
        session = get_session(session_id)
        if not session:
            raise HTTPException(404, "Session not found")
        
        feedback = feedback_service.analyze_interview(
            job_title=session.job_title,
            history=session.history or [],
            resume_text=session.resume_text or ""
        )
        
        session.feedback = {
            "overall_score": feedback.overall_score,
            "dimensions": feedback.dimensions,
            "summary": feedback.summary
        }
        session.ended_at = datetime.utcnow()
        update_session(session)

        # 重點 3：在終端機漂亮地列印回饋報告
        print("\n" + "="*50)
        print(f"📊 面試回饋報告 - {session.job_title}")
        print("="*50)
        print(f"🏆 總體評分: {feedback.overall_score} / 100")
        print("-" * 30)
        print("📈 各項維度評分:")
        for dim, score in feedback.dimensions.items():
            print(f"  - {dim}: {score}")
        print("-" * 30)
        print("👍 優點:")
        for s in feedback.strengths:
            print(f"  * {s}")
        print("-" * 30)
        print("💪 建議改進:")
        for imp in feedback.improvements:
            print(f"  * {imp}")
        print("-" * 30)
        print(f"📝 總結:\n{feedback.summary}")
        print("="*50 + "\n")
        
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
    
    except Exception as e:
        raise HTTPException(500, f"回饋生成失敗: {str(e)}")
    