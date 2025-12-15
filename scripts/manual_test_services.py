# manual_test_services.py

import os
import sys
import asyncio

#這行是為了讓腳本能找到 backend 模組
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.ocr_service import OCRProcessor
from backend.services.speech_service import SpeechService
from backend.services.agent_service import AgentService
from backend.services.session_service import SessionService
from backend.config import settings

async def main():
    print("=== 開始 Service 層測試 ===")

    # --- 1. 測試 OCR (眼睛) ---
    print("\n[1] 測試 OCR Service...")
    ocr = OCRProcessor()
    # 請確保根目錄有這張測試圖，或是修改路徑
    test_resume_path = "test_resume.pdf" 
    
    if os.path.exists(test_resume_path):
        success, result = ocr.process_file(test_resume_path)
        if success:
            print(f"✅ OCR 成功，抓到 {result['summary']['total_characters']} 個字")
            full_text = result['pages'][0]['full_text']
        else:
            print(f"❌ OCR 失敗: {result}")
            return
    else:
        print(f"⚠️ 找不到 {test_resume_path}，跳過 OCR 測試")
        full_text = "我是測試工程師，擅長 Python 與 Unity 開發。" # 假資料

    # --- 2. 測試 Agent (大腦 - 推斷職位) ---
    print("\n[2] 測試 Agent Service (推斷職位)...")
    agent = AgentService()
    job_title = agent.infer_job(full_text)
    print(f"✅ 推斷職位: {job_title}")

    # --- 3. 測試 Session (記憶) ---
    print("\n[3] 測試 Session Service...")
    session_id = SessionService.create_session(job_title, full_text)
    print(f"✅ Session ID: {session_id}")

    # --- 4. 測試 STT (耳朵) ---
    print("\n[4] 測試 Speech Service (STT)...")
    speech = SpeechService()
    test_audio_path = "test_audio.wav" # 請確保根目錄有這個檔案
    
    user_text = ""
    if os.path.exists(test_audio_path):
        user_text = speech.speech_to_text(test_audio_path)
        print(f"✅ STT 轉錄結果: {user_text}")
    else:
        print(f"⚠️ 找不到 {test_audio_path}，使用模擬回答")
        user_text = "我有三年的 Python 開發經驗。"

    # --- 5. 測試 Agent (大腦 - 生成問題) ---
    print("\n[5] 測試 Agent Service (生成問題)...")
    # 模擬把用戶回答塞入歷史
    SessionService.add_history(session_id, "請做個自我介紹", user_text)
    
    question = agent.generate_question(session_id)
    print(f"✅ AI 生成下一題: {question}")

    print("\n=== 測試完成 ===")

if __name__ == "__main__":
    asyncio.run(main())
    