# backend/services/session_service.py
from backend.database import SessionLocal, InterviewSession
from uuid import UUID
from typing import Optional, Union

def create_session(
    user_id: Union[UUID, str], 
    job_title: str, 
    resume_id: Optional[Union[UUID, str]] = None, 
    resume_text: str = ""
) -> InterviewSession:
    """
    建立新的面試 Session
    
    Args:
        user_id: 使用者 ID (接受 str 或 UUID)
        job_title: 應徵職位
        resume_id: 履歷 ID (可選)
        resume_text: 履歷文字內容
        
    Returns:
        InterviewSession: 建立的 session 物件
    """
    # 統一轉為字串
    if isinstance(user_id, UUID):
        user_id = str(user_id)
    if isinstance(resume_id, UUID):
        resume_id = str(resume_id)
    
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


def get_session(session_id: Union[UUID, str]) -> Optional[InterviewSession]:
    """
    取得指定的面試 Session
    
    Args:
        session_id: Session ID (接受 str 或 UUID)
        
    Returns:
        InterviewSession or None: Session 物件
    """
    # 統一轉為字串
    if isinstance(session_id, UUID):
        session_id = str(session_id)
    
    with SessionLocal() as db:
        session = db.query(InterviewSession).filter(
            InterviewSession.id == session_id
        ).first()
        
        if session:
            # 確保 history 是 list
            if session.history is None:
                session.history = []
            
            db.expunge(session)  # 從 session 中分離，避免 detached 錯誤
        
        return session


def update_session(session: InterviewSession) -> bool:
    """
    更新面試 Session
    
    Args:
        session: 要更新的 session 物件
        
    Returns:
        bool: 是否更新成功
    """
    try:
        with SessionLocal() as db:
            # 先查詢現有的 session
            existing = db.query(InterviewSession).filter(
                InterviewSession.id == session.id
            ).first()
            
            if not existing:
                print(f"[Session] 找不到 Session: {session.id}")
                return False
            
            # 更新欄位
            existing.current_question = session.current_question
            existing.question_count = session.question_count
            existing.history = session.history
            existing.resume_text = session.resume_text
            existing.ended_at = session.ended_at
            existing.feedback = session.feedback
            
            db.commit()
            db.refresh(existing)
            
            # 更新傳入的 session 物件
            session.current_question = existing.current_question
            session.question_count = existing.question_count
            session.history = existing.history
            
        return True
        
    except Exception as e:
        print(f"[Session] 更新失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def delete_session(session_id: Union[UUID, str]) -> bool:
    """
    刪除面試 Session
    
    Args:
        session_id: Session ID (接受 str 或 UUID)
        
    Returns:
        bool: 是否刪除成功
    """
    # 統一轉為字串
    if isinstance(session_id, UUID):
        session_id = str(session_id)
    
    try:
        with SessionLocal() as db:
            session = db.query(InterviewSession).filter(
                InterviewSession.id == session_id
            ).first()
            
            if session:
                db.delete(session)
                db.commit()
                return True
            
            return False
            
    except Exception as e:
        print(f"[Session] 刪除失敗: {e}")
        return False


# ✅ 匯出所有函數
__all__ = ["create_session", "get_session", "update_session", "delete_session"]