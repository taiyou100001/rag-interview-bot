# agents.py (完整增強版 - 加入問題去重)
import ollama

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
            print(f"錯誤: {e}")
            return None
    
    def _convert_to_traditional(self, text: str) -> str:
        """簡轉繁（常見字詞）"""
        conversions = {
            '什么': '什麼', '怎么': '怎麼', '这': '這', '那个': '那個',
            '个': '個', '为': '為', '过': '過', '么': '麼',
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
        
        prompt = f"""你是台灣的專業面試官，請用繁體中文生成面試問題。

應徵職位：{job}
履歷摘要：{resume[:400]}

{history_context}

本輪問題類型：{question_type}

要求：
1. 使用繁體中文（台灣用語）
2. 直接提出問題，不要前言
3. 問題具體且專業
4. 避免使用簡體中文字詞

請生成面試問題："""
        
        return self.run_llm(prompt, temperature=0.7)
    
    def _get_question_type(self, count):
        """根據問題數量決定類型"""
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
    
    def __init__(self, knowledge_engine):
        super().__init__()
        self.knowledge_engine = knowledge_engine
        self.max_retry = 2  # 最多重試次數
    
    def generate_question(self, job: str, resume: str, history: list):
        """基於知識庫動態生成問題（含去重機制）"""
        
        attempts = 0
        while attempts < self.max_retry:
            # 決定考核重點
            focus = self._determine_focus(len(history))
            
            # 從知識庫檢索相關知識
            try:
                knowledge = self.knowledge_engine.get_relevant_knowledge(
                    query=f"{job} {focus}",
                    job_title=job,
                    top_k=2
                )
            except Exception as e:
                print(f"知識庫檢索失敗: {e}")
                knowledge = []
            
            # 建構知識上下文
            knowledge_context = self._build_knowledge_context(knowledge)
            
            # 建議修改：傳遞最近幾輪的完整問答
            history_context = ""
            if history:
                recent_history = history[-2:] # 傳遞最近兩次的問答
                history_context = "\n過去對話：\n"
                for turn in recent_history:
                    history_context += f"Q: {turn['question']}\nA: {turn['answer']}\n---\n"
            
            # 生成問題
            prompt = f"""你是台灣的專業面試官，請根據知識點生成原創面試問題。

應徵職位：{job}
本輪考核重點：{focus}

相關知識參考：
{knowledge_context}

履歷摘要：{resume[:800]}
{history_context}

要求：
1. 僅生成一個問題，請勿使用編號列表 (如 1., 2. 等)
2. 基於知識點設計問題，但不要直接複製
3. 問題要具體、可評估
4. 適合口頭回答
5. 使用繁體中文（台灣用語）
6. 直接輸出問題，無前言
7. 問題要與之前的問題不同
8. 如果你檢視到履歷中的經驗或先前的回答是模糊、空泛、或用戶承認是假設性的，請設計一個更深入的追問，或將問題從「你做過什麼」轉向「你會怎麼做」。

請生成面試問題："""
            
            # 提高溫度增加多樣性
            temperature = 0.8 + (attempts * 0.1)
            question = self.run_llm(prompt, temperature=temperature)
            
            if not question:
                return None
            
            # 檢查是否與歷史問題重複
            if not self.knowledge_engine.is_question_similar(question, history):
                return question
            
            print(f"  (問題重複，重新生成... 第 {attempts + 1} 次)")
            attempts += 1
        
        # 如果都重複，還是返回最後一個
        return question
    
    def _determine_focus(self, count):
        """決定考核重點"""
        focuses = [
            "基礎概念理解和應徵動機",
            "實際工作經驗和專案案例",
            "技術深度和專業能力",
            "問題解決和架構思維",
            "團隊協作和溝通能力"
        ]
        
        if count < len(focuses):
            return focuses[count]
        return "綜合能力評估"
    
    def _build_knowledge_context(self, knowledge_items):
        """建構知識上下文"""
        if not knowledge_items:
            return "(無特定知識參考)"
        
        context_parts = []
        for item in knowledge_items:
            if item['type'] == 'skill':
                context_parts.append(
                    f"技能領域：{item['area']}\n"
                    f"核心概念：{', '.join(item['concepts'][:3])}\n"
                    f"評估重點：{', '.join(item['evaluation'][:2])}"
                )
            else:
                context_parts.append(
                    f"評估維度：{item['dimension']}\n"
                    f"階段：{' → '.join(item['stages'])}"
                )
        
        return "\n\n".join(context_parts)