# interview_router.py

import os
import shutil
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from backend.models.pydantic_models import QuestionResponse
from backend.services.session_service import SessionService
from backend.services.agent_service import AgentService
from backend.services.speech_service import SpeechService
from backend.config import settings

router = APIRouter()
agent_service = AgentService()
speech_service = SpeechService()

# --- Helper Functions (輔助函式) ---

def process_audio_file(session_id: str, audio_file: UploadFile) -> str:
    """
    處理音檔儲存與 STT 辨識，並確保暫存檔被刪除 (來自重構版)
    """
    if not audio_file:
        return ""
    
    temp_filename = f"temp_{session_id}.wav"
    temp_path = os.path.join(settings.AUDIO_DIR, temp_filename)
    user_text = ""

    try:
        # 儲存檔案
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
        
        # 執行 STT
        user_text = speech_service.speech_to_text(temp_path)
    except Exception as e:
        print(f"STT Error: {e}")
    finally:
        # 清理暫存檔 (重構版優化：確保一定會刪除)
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
    return user_text

def check_voice_command(text: str) -> Optional[str]:
    """
    檢查文字中是否包含下一題或退出的指令 (來自重構版的新功能)
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

# --- Main Endpoint ---

@router.post("/answer", response_model=QuestionResponse)
async def submit_answer(
    session_id: str = Form(...),    
    audio_file: UploadFile = File(None) 
):
    # 1. 驗證 Session
    session = SessionService.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 2. 處理音檔 (STT) - 使用 Helper Function
    user_text = process_audio_file(session_id, audio_file)
    print(f"🎤 使用者說: {user_text}")

    # 3. 🔥 指令判斷邏輯 (合併自重構版)
    command = check_voice_command(user_text)

    if command == "EXIT":
        print("🛑 偵測到退出指令")
        return QuestionResponse(
            question_text="好的，今天的面試到此結束，辛苦了。",
            is_end=True 
        )

    elif command == "NEXT":
        print("⏭️ 偵測到下一題指令，略過本次回答")
        # 覆蓋 user_text，讓 AI 知道使用者想換題
        user_text = "（使用者要求跳過此題，請直接提供下一個不同的面試問題）"

    # 4. 更新歷史紀錄 (儲存使用者的回答)
    # 注意：必須在生成下一題「之前」存入，這樣 Agent 才能讀到上下文
    if user_text:
        last_history = session.get('history', [])
        if last_history:
             last_history[-1]['answer'] = user_text

    # 5. 生成下一題 (AI)
    question_text = agent_service.generate_question(session_id)

    print(f"========================================")
    print(f" AI 生成的題目: {question_text}")
    print(f"========================================")
    
    if not question_text:
        return QuestionResponse(question_text="面試結束，感謝您的參與。", is_end=True)

    # 6. 存入新問題
    SessionService.add_history(session_id, question_text, "")

    # 7. 回傳結果
    return QuestionResponse(
        question_text=question_text,
        is_end=False
    )