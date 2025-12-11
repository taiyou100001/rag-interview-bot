# session_services.py

import uuid
from typing import Dict, Any

# 用一個全域變數暫存 (正式環境通常用 Redis，但現在先求跑通)
sessions_db: Dict[str, Dict[str, Any]] = {}

class SessionService:
    @staticmethod
    def create_session(job_title: str, resume_text: str) -> str:
        session_id = str(uuid.uuid4())
        sessions_db[session_id] = {
            "job_title": job_title,
            "resume_text": resume_text,
            "history": [],
            "turn_count": 0
        }
        print(f"Session Created: {session_id}")
        return session_id

    @staticmethod
    def get_session(session_id: str):
        return sessions_db.get(session_id)

    @staticmethod
    def add_history(session_id: str, question: str, answer: str):
        if session_id in sessions_db:
            sessions_db[session_id]["history"].append({
                "question": question,
                "answer": answer
            })
            sessions_db[session_id]["turn_count"] += 1