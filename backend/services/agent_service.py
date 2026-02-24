# backend/services/agent_service.py
import ollama
from typing import List, Optional

# 設定使用的模型
MODEL = "llama3.1:8b"

class BaseAgent:
    """基礎 Agent 類別"""
    def __init__(self, model=MODEL):
        self.model = model

    def run_llm(self, prompt, temperature=0.5):
        """呼叫 LLM，強制使用繁體中文"""
        full_prompt = f"""你必須使用繁體中文（台灣用語）回答，不可使用簡體中文。

{prompt}

請務必使用繁體中文回答。"""

        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': '你是台灣的專業面試官，只使用繁體中文（台灣用語）進行溝通。'},
                    {'role': 'user', 'content': full_prompt}
                ],
                options={'temperature': temperature, 'num_predict': 512}
            )
            result = response['message']['content'].strip()
            return self._convert_to_traditional(result)
        except Exception as e:
            print(f"LLM 呼叫錯誤: {e}")
            return None
    
    def _convert_to_traditional(self, text: str) -> str:
        """簡轉繁（常見字詞補強）"""
        conversions = {
            '什么': '什麼', '怎么': '怎麼', '这': '這', '那个': '那個',
            '个': '個', '为': '為', '过': '過', '么': '麼',
            '不仅': '不僅', '网络': '網路', '程序': '程式', '项目': '專案'
            }
        for simp, trad in conversions.items():
            text = text.replace(simp, trad)
        return text

class JobInferenceAgent(BaseAgent):
    """職位推斷 Agent"""
    def infer_job_title(self, resume_text: str, structured_resume: dict = None):
        """根據履歷推斷職位"""
        if structured_resume and 'job_title' in structured_resume:
            job_title = structured_resume.get('job_title', '').strip()
            if job_title and len(job_title) > 2:
                return job_title
        
        prompt = f"""根據以下履歷內容推斷應徵職位，只需回答職位名稱：

{resume_text[:1000]}

應徵職位："""
        
        output = self.run_llm(prompt, temperature=0.1)
        if output and len(output) < 50:
            return output.strip().replace('應徵職位', '').replace('：', '').replace(':', '').strip()
        return "未知職位"


# ==========================================
# 乾淨的介面：保留 AgentService 讓舊程式呼叫不報錯
# ==========================================
class AgentService:
    def __init__(self):
        # 移除了所有會報錯的 RAG 與 Session 依賴
        self.job_agent = JobInferenceAgent()

    def infer_job(self, resume_text: str) -> str:
        """推斷職位"""
        return self.job_agent.infer_job_title(resume_text)

    def generate_question(self, session_id: str) -> Optional[str]:
        # 新架構已不再使用此處生成題目，放一個防呆提示
        print("⚠️ 提醒: 面試流程已升級至 enhanced_agent_service")
        return "請簡述您的相關經驗。"