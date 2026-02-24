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
    
    def _build_system_prompt(self, persona: str = "neutral"):
        base_role = (
            "你是一位台灣的專業技術面試官，僅使用繁體中文（台灣用語）溝通。"
            "你的職責是根據面試目標提出具體、可評估、可口頭回答的問題，並維持專業、精確、尊重的語氣。"
        )

        persona_map = {
            "friendly": "風格：友善且鼓勵，會短句正向回饋，並以引導式問題協助受試者展現強項。",
            "strict": "風格：嚴格且注重細節，偏向技術深挖與邏輯驗證，避免冗語。",
            "neutral": "風格：中立且專業，聚焦能力評估與場景化問題。",
            "casual": "風格：輕鬆且對話式，以自然互動引出經驗與案例。"
        }
        persona_desc = persona_map.get(persona, persona_map["neutral"])

        global_rules = (
            "通用規範：\n"
            "- 問題需具體、可驗證，鼓勵舉例或描述步驟、指標、取捨。\n"
            "- 僅輸出面試問題與必要追問；不加入額外敘述或解釋。\n"
            "- 不使用編號或列表記號；每次輸出最多兩行（主問題 + 追問）。\n"
            "- 維持尊重與包容，避免偏見與不當問題。"
        )

        return f"{base_role}\n{persona_desc}\n{global_rules}"

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
        
        prompt = f"""
                [CONTEXT]
                - 應徵職位：{job_title}
                - 履歷摘要：{resume_text[:800]}
                - 歷史互動： {history}

                [TASK]
                生成一個與本輪焦點高度對齊的原創面試問題；若候選人可能給出抽象或不完整回答，請附上一句追問以促進具體化。

                [INSTRUCTIONS]
                - 僅輸出面試問題與（可選）追問；不加入說明、列表、編號、前綴。
                - 問題需包含評估維度（如指標、步驟、案例、取捨、風險）。
                - 追問以「追問：」開頭，僅一行。
                - 語言：繁體中文（台灣用語）。

                [OUTPUT FORMAT]
                - 第一行：主問題（單行）
                - 第二行（可選）：追問（單行，以「追問：」開頭）

                [EXAMPLES]
                - 主問題：若要在 Meta Quest 3 上以 Unity 建置低延遲語音互動，你會如何在 AudioInput、前處理、串流傳輸與 FastAPI 接收端設計緩衝與重試機制？請以一個實作案例說明監控指標與瓶頸。
                - 追問：當網路抖動導致分段丟失時，你如何在協定或緩衝策略上補償並確保語義完整？

                - 主問題：在 RAG 面試系統中，如何設計檔案分塊與檢索評分，以避免知識幻覺並提升問答相關性？請描述你會追蹤的評估指標與容錯策略。
                - 追問：若檢索結果相互矛盾，你的重排序與置信度合併策略是什麼？

                [GENERATE]
                請依照上述格式輸出。
                """

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