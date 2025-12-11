# interview_router.py

import os
import shutil
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from backend.models.pydantic_models import QuestionResponse
from backend.services.session_service import SessionService
from backend.services.agent_service import AgentService
from backend.services.speech_service import SpeechService
from backend.config import settings

router = APIRouter()
agent_service = AgentService()
speech_service = SpeechService()

@router.post("/answer", response_model=QuestionResponse)
async def submit_answer(
    # 接收 Unity 傳來的資料：
    # 1. session_id (字串，用來識別是用戶)
    # 2. audio_file (檔案，Unity 錄製的 .wav，允許為空如果是第一題)
    session_id: str = Form(...),    
    audio_file: UploadFile = File(None) 
):
    # --- 步驟 1: 驗證 Session 是否存在 ---
    session = SessionService.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    user_text = ""
    
    # --- 步驟 2: 處理使用者語音 (STT) ---
    # 只有當 Unity 有傳錄音檔過來時才執行
    if audio_file:
        # 暫存音檔到硬碟 (因為 Azure STT 需要讀取檔案路徑)
        temp_filename = f"temp_{session_id}.wav"
        temp_path = os.path.join(settings.AUDIO_DIR, temp_filename)
        
        try:
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(audio_file.file, buffer)
                
            # 呼叫 Azure STT 服務 (語音 -> 文字)
            user_text = speech_service.speech_to_text(temp_path)
            
        except Exception as e:
            print(f"STT Error: {e}")
        finally:
            # 轉錄完成後刪除暫存檔，保持伺服器乾淨
            if os.path.exists(temp_path):
                os.remove(temp_path)

    # --- 步驟 3: 更新對話歷史 ---
    # 如果有成功轉錄出文字，把它補到上一題的回答欄位
    if user_text:
        last_history = session['history']
        if last_history:
             last_history[-1]['answer'] = user_text
        print(f"用戶回答: {user_text}") # Debug 用
    
    # --- 步驟 4: AI 生成下一題 (LLM + RAG) ---
    question_text = agent_service.generate_question(session_id)
    
    # 如果生成失敗或面試結束
    if not question_text:
        return QuestionResponse(
            question_text="面試已結束，感謝您的參與。", 
            audio_url="", 
            is_end=True
        )

    # 將新問題存入 Session 歷史 (等待下次用戶回答)
    SessionService.add_history(session_id, question_text, "")

    # --- 步驟 5: 題目轉語音 (TTS) ---
    # 這裡會生成 mp3/wav 檔案存到 static/audio 資料夾
    # 並且回傳 "相對路徑字串" (例如: /static/audio/uuid.wav)
    audio_url = speech_service.text_to_speech(question_text)
    
    # --- 步驟 6: 回傳 JSON ---
    # 注意：這裡只回傳 URL 字串，Unity 收到後要自己去下載
    return QuestionResponse(
        question_text=question_text,
        audio_url=audio_url,
        is_end=False
    )
