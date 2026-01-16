# backend/services/enhanced_agent_service.py
from ollama import Client
from typing import List, Dict
import json

class EnhancedInterviewAgent:
    """增強版面試代理,支援閒聊、追問與個性化"""
    
    def __init__(self, personality: str = "friendly"):
        self.client = Client()
        self.model = 'llama3.1:8b'
        self.personality = personality
        self.max_questions = 10
        
        # 面試官個性模板
        self.personality_prompts = {
            "friendly": "你是一位友善、鼓勵型的面試官,會適時給予正面回饋並引導求職者展現優勢。",
            "strict": "你是一位嚴格、注重細節的面試官,會深入追問技術細節與實作經驗。",
            "neutral": "你是一位中立、專業的面試官,客觀評估求職者能力並提出具體問題。",
            "casual": "你是一位輕鬆、對話式的面試官,營造自然氛圍並從日常對話中觀察求職者。"
        }
    
    def _build_system_prompt(self, job_title: str) -> str:
        """建構系統提示詞"""
        base_prompt = self.personality_prompts.get(self.personality, self.personality_prompts["friendly"])
        return f"""{base_prompt}

**面試職位**: {job_title}

**對話原則**:
1. 若求職者回答過於簡短或緊張,可先進行簡單閒聊(如興趣、最近狀況)緩解氣氛
2. 根據履歷內容提出具體追問(例:"您提到熟悉Vue.js,請說明其生命週期...")
3. 若求職者偏離主題,溫和引導回正題
4. 每次回應控制在50-80字,保持自然對話感
5. 面試結束前給予初步評價與建議

**輸出格式**:
請直接輸出下一個問題或回應,不要包含任何標記。"""

    def generate_first_question(self, job_title: str, resume_text: str = "") -> str:
        """生成第一個問題(破冰)"""
        prompt = f"""你正在面試一位應徵 {job_title} 的求職者。
履歷摘要: {resume_text[:500]}

請生成一個友善的破冰問題,例如:
- "歡迎!請先用1-2分鐘簡單介紹自己,以及為什麼想應徵這個職位?"
- "您好!看到您的履歷很豐富,能先聊聊您最近在忙些什麼嗎?"

請只輸出問題本身,不要有其他說明。"""

        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': self._build_system_prompt(job_title)},
                    {'role': 'user', 'content': prompt}
                ],
                options={'temperature': 0.7}
            )
            return response['message']['content'].strip()
        except Exception as e:
            print(f"[ERROR] 生成第一題失敗: {e}")
            return f"您好!很高興能與您進行 {job_title} 的面試。請先用1分鐘簡單介紹您自己吧!"

    def generate_question(
        self, 
        job_title: str, 
        resume_text: str, 
        history: List[Dict],
        context: str = ""
    ) -> str | None:
        """生成下一個問題或閒聊回應
        
        Args:
            job_title: 職位名稱
            resume_text: 履歷內容
            history: 對話歷史 [{question, answer}, ...]
            context: RAG檢索到的額外上下文
        
        Returns:
            下一個問題或None(結束面試)
        """
        if len(history) >= self.max_questions:
            return None
        
        # 分析最近3輪對話
        recent_qa = history[-3:] if len(history) >= 3 else history
        qa_text = "\n".join([
            f"Q{i+1}: {qa['question']}\nA{i+1}: {qa['answer']}"
            for i, qa in enumerate(recent_qa)
        ])
        
        # 判斷是否需要閒聊(回答過短或緊張)
        last_answer = history[-1]['answer'] if history else ""
        needs_chitchat = len(last_answer) < 20 or "不太清楚" in last_answer or "不太會" in last_answer
        
        prompt = f"""**當前情境**:
- 職位: {job_title}
- 已進行: {len(history)}/{self.max_questions} 輪
- 履歷摘要: {resume_text[:800]}

**最近對話**:
{qa_text}

**RAG知識庫提示**: {context[:300] if context else "無"}

**判斷**: {"求職者似乎緊張或回答簡短,可先進行輕鬆閒聊" if needs_chitchat else "繼續深入提問"}

請生成下一個回應:
1. 若需閒聊,可詢問興趣、近況、壓力狀況等緩解氣氛
2. 若繼續提問,應根據履歷與前述回答進行追問
3. 控制在60字以內,保持自然對話感

直接輸出問題/回應,無需說明。"""

        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': self._build_system_prompt(job_title)},
                    {'role': 'user', 'content': prompt}
                ],
                options={'temperature': 0.8, 'num_predict': 150}
            )
            return response['message']['content'].strip()
        except Exception as e:
            print(f"[ERROR] 生成問題失敗: {e}")
            return "請分享您在上一份工作中最有挑戰性的經驗?"

    def generate_feedback(self, job_title: str, history: List[Dict]) -> str:
        """生成面試總結與回饋"""
        qa_summary = "\n".join([
            f"Q: {qa['question'][:50]}...\nA: {qa['answer'][:100]}..."
            for qa in history[:5]  # 取前5輪
        ])
        
        prompt = f"""請針對這場 {job_title} 面試提供專業回饋:

**面試摘要**:
{qa_summary}

請從以下角度評估(控制在200字內):
1. **表達能力**: 回答是否清晰、有條理?
2. **專業能力**: 是否展現相關技能與經驗?
3. **改進建議**: 具體可提升的方向

請用友善語氣輸出,格式為:
【整體表現】...
【優點】...
【建議】..."""

        try:
            response = self.client.chat(
                model=self.model,
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.5, 'num_predict': 300}
            )
            return response['message']['content'].strip()
        except Exception as e:
            print(f"[ERROR] 生成回饋失敗: {e}")
            return "感謝您的參與!您的表現展現了不錯的基礎,建議可多準備具體案例來強化說服力。"


class AgentFactory:
    """工廠模式管理多種面試官個性"""
    
    @staticmethod
    def get_agent(job_title: str = "軟體工程師", personality: str = "friendly"):
        """
        Args:
            job_title: 職位(用於未來擴展職位特化邏輯)
            personality: friendly, strict, neutral, casual
        """
        return EnhancedInterviewAgent(personality=personality)


# 全局實例
agent_factory = AgentFactory()