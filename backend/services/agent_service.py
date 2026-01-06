# agent_service.py

import ollama
import re
from typing import List, Optional
from backend.services.rag_service import RagService
from backend.services.session_service import SessionService

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
                print(f"從結構化資料取得職位: {job_title}")
                return job_title
        
        prompt = f"""根據以下履歷內容推斷應徵職位，只需回答職位名稱：

{resume_text[:400]}

應徵職位："""
        print("正在推斷職位...")
        output = self.run_llm(prompt, temperature=0.1)
        
        if output and len(output) < 50:
            cleaned = output.strip().replace('應徵職位', '').replace('：', '').replace(':', '').strip()
            return cleaned
        
        return None


class QuestionGeneratorAgent(BaseAgent):
    """問題生成 Agent（不使用 RAG）"""
    def __init__(self, fixed_difficulty: str = None):
        super().__init__()
        self.fixed_difficulty = fixed_difficulty

    def generate_question(self, job: str, resume: str, history: list):
        """生成面試問題"""
        question_type = self._get_question_type(len(history))
        
        history_context = ""
        if history:
            recent = history[-2:]
            history_context = "先前對話：\n"
            for turn in recent:
                history_context += f"問題：{turn['question'][:60]}\n"
                history_context += f"回答：{turn['answer'][:60]}\n"
        
        difficulty = self.fixed_difficulty if self.fixed_difficulty else "medium"

        prompt = f"""你是台灣的專業面試官，請用繁體中文生成面試問題。

應徵職位：{job}
履歷摘要：{resume[:400]}

{history_context}

本輪問題類型：{question_type}

要求：
1. 僅生成一個問題，請勿使用編號列表
2. 基於知識點設計問題，但不要直接複製
3. 問題要具體、可評估
4. 適合口頭回答
5. 使用繁體中文（台灣用語）
6. 發問前先以和善的語氣閒聊，再發問
7. 問題要與之前的問題不同

請生成面試問題："""

        return self.run_llm(prompt, temperature=0.7)
    
    def _get_question_type(self, count):
        types = [
            "開場問題 - 了解應徵動機與職涯規劃",
            "履歷深挖 - 針對過往工作經驗提問",
            "專業技能 - 評估核心能力",
            "行為問題 - 詢問具體案例",
            "情境問題 - 測試應變與問題解決能力"
        ]
        return types[count] if count < len(types) else "綜合能力評估"


class KnowledgeBasedQuestionAgent(BaseAgent):
    """基於知識庫的問題生成 Agent（使用 RAG + 去重）"""
    
    def __init__(self, knowledge_engine, fixed_difficulty: str = None):
        super().__init__()
        self.knowledge_engine = knowledge_engine
        self.max_retry = 2  # 最多重試次數
        self.fixed_difficulty = fixed_difficulty  # 使用者指定的難度（None 表示自動遞進）
    
    def generate_question(self, job: str, resume: str, history: list):
        """基於知識庫動態生成問題（含去重機制和難度級別）"""
        
        attempts = 0
        while attempts < self.max_retry:
            # 決定考核重點
            focus = self._determine_focus(len(history))
            
            # 決定難度級別 (HEAD 邏輯)
            if self.fixed_difficulty:
                difficulty = self.fixed_difficulty
            else:
                difficulty = self._determine_difficulty(len(history))
            
            # 從知識庫檢索相關知識
            # 合併策略：使用 Vivi 的方法簽名，但嘗試將難度邏輯納入查詢
            try:
                # 這裡假設 rag_engine 可能不支援 difficulty 參數，因此將難度加入 query 字串
                query_text = f"{job} {focus} {difficulty}"
                knowledge = self.rag_engine.get_relevant_knowledge(
                    query=query_text,
                    job_title=job,
                    top_k=2
                )
            except Exception as e:
                print(f"RAG 檢索失敗（Redis 可能未啟動，已自動降級）: {e}")
                knowledge = []  # 降級為無知識庫模式
            
            # 建構知識上下文
            knowledge_context = self._build_knowledge_context(knowledge, difficulty)
            
            # 組裝歷史對話
            history_context = ""
            if history:
                recent = history[-2:]
                history_context = "\n過去對話：\n"
                for turn in recent:
                    history_context += f"Q: {turn['question']}\nA: {turn['answer']}\n---\n"
            
            # Prompt (合併難度要求與上下文長度)
            prompt = f"""你是台灣的專業面試官，請根據知識點生成原創面試問題。

應徵職位：{job}
本輪考核重點：{focus}
難度級別：{difficulty}

相關知識參考：
{knowledge_context}

履歷摘要：{resume[:600]}
{history_context}

要求：
1. 基於知識點設計問題，但不要直接複製
2. 問題要具體、可評估
3. 適合口頭回答
4. 使用繁體中文（台灣用語）
5. 發問前先以和善的語氣閒聊，再發問
6. 問題要與之前的問題不同
7. 問題難度要符合「{difficulty}」級別
8. 如果用戶回答模糊，請設計追問

請生成面試問題："""
            
            # 提高溫度增加多樣性
            temperature = 0.7 + (attempts * 0.1)
            question = self.run_llm(prompt, temperature=temperature)
            
            if not question:
                return "請簡述您的相關經驗。"
            
            # 檢查是否與歷史問題重複 (使用比對邏輯)
            if len(history) == 0 or not self._is_duplicate(question, history):
                return question
            
            print(f" (問題重複，重新生成... 第 {attempts + 1} 次)")
            attempts += 1
        
        # 如果都重複，還是返回最後一個
        return question
    
    def _determine_difficulty(self, count):
        """決定難度級別（根據問題輪數遞進，來自 HEAD）"""
        difficulties = [
            "easy",      # 第 0 題
            "easy",      # 第 1 題
            "medium",    # 第 2 題
            "medium",    # 第 3 題
            "hard",      # 第 4 題
        ]
        
        if count < len(difficulties):
            return difficulties[count]
        return "hard"  # 之後都是 hard
    
    def _is_duplicate(self, new_q: str, history: list) -> bool:
        """簡單字面相似度檢查"""
        if not history:
            return False
        
        def get_tokens(text):
            return set(text.replace(" ", "").replace("？", "").replace("，", ""))

        new_tokens = get_tokens(new_q)
        for h in history[-3:]: # 只檢查最近 3 題
            old_tokens = get_tokens(h['question'])
            if not new_tokens or not old_tokens:
                continue
            
            intersection = new_tokens.intersection(old_tokens)
            union = new_tokens.union(old_tokens)
            similarity = len(intersection) / len(union) if union else 0.0
            
            if similarity > 0.6: # 超過 60% 字元重疊視為重複
                return True
        return False

    def _determine_focus(self, count):
        """決定考核重點"""
        focuses = [
            "應徵動機與自我介紹",
            "核心專案經驗",
            "技術深度與實作細節",
            "問題解決能力",
            "團隊協作與溝通"
        ]
        return focuses[count] if count < len(focuses) else "綜合能力評估"
    
    def _build_knowledge_context(self, knowledge_items, difficulty: str = "medium"):
        """建構知識上下文（使用 HEAD 較豐富的邏輯）"""
        if not knowledge_items:
            return "(無特定知識參考)"
        
        context_parts = []
        for item in knowledge_items:
            if item.get('type') == 'skill':
                part = f"技能領域：{item.get('area')}\n"
                concepts = item.get('concepts', [])
                part += f"核心概念：{', '.join(concepts[:3])}\n"
                
                # 如果有難度提示，加入
                if 'difficulty_hint' in item:
                    part += f"提問方向（{difficulty}）：{item['difficulty_hint']}"
                
                context_parts.append(part)
            else:
                context_parts.append(
                    f"評估維度：{item.get('dimension')}\n"
                    f"階段：{' → '.join(item.get('stages', []))}"
                )
        
        return "\n\n".join(context_parts)


# === 對外服務入口===
class AgentService:
    def __init__(self):
        self.rag_engine = RagService()
        # 這裡將 KnowledgeBasedQuestionAgent 初始化，並傳入 RAG 引擎
        self.question_agent = KnowledgeBasedQuestionAgent(self.rag_engine)
        self.job_agent = JobInferenceAgent()

    def generate_question(self, session_id: str) -> Optional[str]:
        """產生下一道面試題目"""
        session = SessionService.get_session(session_id)
        if not session:
            print(f"錯誤：Session {session_id} 不存在")
            return None

        job = session['job_title']
        history = session['history']
        resume = session['resume_text']
        
        return self.question_agent.generate_question(job, resume, history)

    def infer_job(self, resume_text: str) -> str:
        """推斷職位"""
        return self.job_agent.infer_job_title(resume_text)
    
