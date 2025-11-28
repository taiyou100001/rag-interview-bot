# agents.py (完整增強版 - 加入問題去重)
import ollama
import re
from typing import List

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
        
        # 如果設定了固定難度，將難度加入 prompt
        difficulty = None
        if hasattr(self, 'fixed_difficulty') and self.fixed_difficulty:
            difficulty = self.fixed_difficulty

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

        # 若有難度資訊，請求 LLM 產生對應難度的題目
        if difficulty:
            prompt = prompt.replace("請生成面試問題：", f"難度級別：{difficulty}\n\n請生成面試問題：")

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
            
            # 決定難度級別
            if self.fixed_difficulty:
                # 使用使用者指定的難度
                difficulty = self.fixed_difficulty
            else:
                # 自動根據問題輪數遞進
                difficulty = self._determine_difficulty(len(history))
            
            # 從知識庫檢索相關知識（根據難度級別）
            try:
                knowledge = self.knowledge_engine.get_relevant_knowledge_by_difficulty(
                    query=f"{job} {focus}",
                    job_title=job,
                    difficulty=difficulty,
                    top_k=2
                )
            except Exception as e:
                print(f"知識庫檢索失敗（Redis 可能未啟動，已自動降級）: {e}")
                knowledge = []  # 降級為無知識庫模式
            
            # 建構知識上下文（包含難度提示）
            knowledge_context = self._build_knowledge_context(knowledge, difficulty)
            
            # 歷史上下文
            history_context = ""
            if history and len(history) > 0:
                last = history[-1]
                history_context = f"\n先前討論過：{last['question'][:40]}"
            
            # 生成問題
            prompt = f"""你是台灣的專業面試官，請根據知識點生成原創面試問題。

應徵職位：{job}
本輪考核重點：{focus}
難度級別：{difficulty}

相關知識參考：
{knowledge_context}

履歷摘要：{resume[:300]}
{history_context}

要求：
1. 基於知識點設計問題，但不要直接複製
2. 問題要具體、可評估
3. 適合口頭回答
4. 使用繁體中文（台灣用語）
5. 直接輸出一個問題，無前言
6. 問題要與之前的問題不同
7. 問題難度要符合「{difficulty}」級別

請生成面試問題："""
            
            # 提高溫度增加多樣性
            temperature = 0.8 + (attempts * 0.1)
            question = self.run_llm(prompt, temperature=temperature)
            
            if not question:
                return None
            
            # 檢查是否與歷史問題重複
            if len(history) == 0 or not any(
                self._simple_similarity(question, h["question"]) > 0.85
                for h in history[-3:]
            ):
                return question
            
            print(f"  (問題重複，重新生成... 第 {attempts + 1} 次)")
            attempts += 1
        
        # 如果都重複，還是返回最後一個
        return question
    
    def _determine_difficulty(self, count):
        """決定難度級別（根據問題輪數遞進）"""
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
    
    # === 修正點 2：新增遺失的 _simple_similarity 方法 ===
    def _simple_similarity(self, s1: str, s2: str) -> float:
        """簡單字面重疊相似度（避免依賴 Redis 或外部套件）"""
        if not s1 or not s2:
            return 0.0
        s1_set = set(s1.replace(" ", "").replace("？", "").replace("，", "").replace("。", ""))
        s2_set = set(s2.replace(" ", "").replace("？", "").replace("，", "").replace("。", ""))
        if not s1_set and not s2_set:
            return 1.0
        intersection = s1_set.intersection(s2_set)
        union = s1_set.union(s2_set)
        return len(intersection) / len(union) if union else 0.0
    
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
    
    def _build_knowledge_context(self, knowledge_items, difficulty: str = "medium"):
        """建構知識上下文（包含難度提示）"""
        if not knowledge_items:
            return "(無特定知識參考)"
        
        context_parts = []
        for item in knowledge_items:
            if item['type'] == 'skill':
                part = f"技能領域：{item['area']}\n"
                part += f"核心概念：{', '.join(item['concepts'][:3])}\n"
                part += f"評估重點：{', '.join(item['evaluation'][:2])}"
                
                # 如果有難度提示，加入
                if 'difficulty_hint' in item:
                    part += f"\n提問方向（{difficulty}）：{item['difficulty_hint']}"
                
                context_parts.append(part)
            else:
                context_parts.append(
                    f"評估維度：{item['dimension']}\n"
                    f"階段：{' → '.join(item['stages'])}"
                )
        
        return "\n\n".join(context_parts)