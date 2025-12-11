from fastapi import APIRouter, HTTPException
from backend.models.pydantic_models import AnswerRequest, QuestionResponse
from backend.services.session_service import SessionService
from backend.services.agent_service import AgentService
from backend.services.speech_service import SpeechService

router = APIRouter()
agent_service = AgentService()
speech_service = SpeechService()

@router.post("/answer", response_model=QuestionResponse)
async def submit_answer(request: AnswerRequest):
    # 1. 驗證 Session
    session = SessionService.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 2. 記錄上一題的回答 (如果有的話)
    if request.answer_text:
        # 這裡假設上一題的問題在 history 的最後一筆，或是第一次回答
        # 為了簡化，我們先產生新問題，實際應用可以做更細的對應
        pass 
        # SessionService.add_history(request.session_id, "上一題題目", request.answer_text)
        # 注意：正確的流程應該是「使用者回答了上一題 -> 系統存檔 -> 系統出下一題」
        # 我們這裡簡化：只要使用者傳話來，我們就把它當作上一題的回覆，存入歷史
        
        # 為了讓 AI 知道上下文，我們需要把用戶的回答加入歷史
        # 但因為我們還沒生成下一題，這裡的邏輯稍微 tricky
        # 簡單做法：我們把這輪對話直接 append 到 history，讓 AgentService 處理
        last_history = session['history']
        if last_history:
             # 更新上一輪的 answer (原本可能是空的)
             last_history[-1]['answer'] = request.answer_text

    # 3. 生成下一題 (AI 思考)
    question_text = agent_service.generate_question(request.session_id)
    
    if not question_text:
        return QuestionResponse(question_text="面試結束，感謝您的參與。", audio_url="", is_end=True)

    # 將新問題加入歷史紀錄 (Answer 暫時為空)
    SessionService.add_history(request.session_id, question_text, "")

    # 4. 轉語音 (TTS)
    audio_url = speech_service.text_to_speech(question_text)
    
    return QuestionResponse(
        question_text=question_text,
        audio_url=audio_url,
        is_end=False
    )
