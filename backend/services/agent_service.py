# backend/services/agent_service.py
from ollama import Client

class BaseInterviewAgent:
    def generate_first_question(self, job_title: str, resume_text: str = "") -> str:
        return f"您好！請先做一個 1 分鐘的自我介紹，並說明您為什麼想應徵 {job_title} 這個職位？"

    def generate_question(self, job_title: str, resume_text: str, history: list) -> str | None:
        # 簡單版：之後你可以換成更強的 multi-agent
        if len(history) >= 10:
            return None  # 面試結束
        
        prompt = f"""
你是資深技術面試官，正在面試 {job_title}。
履歷摘要：{resume_text[:1000]}
對話紀錄：{history[-3:]}
請提出下一題有鑑別度的技術或行為題，控制在 60 字以內。
"""
        try:
            client = Client()
            response = client.chat(model='llama3.1:8b', messages=[{'role': 'user', 'content': prompt}])
            return response['message']['content'].strip()
        except Exception as e:
            return f"請分享您在上一份工作中最有挑戰性的一個專案？（錯誤：{e}）"

class AgentFactory:
    def get_agent(self, job_title: str = "軟體工程師"):
        return BaseInterviewAgent()

# 必須有這行！
agent_factory = AgentFactory()