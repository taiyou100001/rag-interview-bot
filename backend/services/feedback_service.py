# backend/services/feedback_service.py
import httpx
from typing import List, Tuple, Optional
from backend.config import OLLAMA_BASE_URL, OLLAMA_MODEL


class FeedbackService:
    """AI 面試回饋生成服務"""
    
    def __init__(self):
        self.ollama_url = f"{OLLAMA_BASE_URL}/api/generate"
        self.model = OLLAMA_MODEL
    
    async def generate_feedback(
        self,
        job: str,
        resume: str,
        interview_history: List[Tuple[str, str]],
        lang: str = "zh"
    ) -> str:
        """
        根據職位、履歷和面試問答歷史,使用 Ollama LLM 生成專業反饋
        
        Args:
            job: 應徵職位名稱
            resume: 履歷重點摘要
            interview_history: 包含 (問題, 回答) 元組的列表
            lang: 反饋語言,'zh' 為繁體中文,'en' 為英文
            
        Returns:
            格式化的反饋報告字串,或錯誤訊息
        """
        if not interview_history or not isinstance(interview_history, list):
            return "❌ 無有效的面試歷史記錄,無法生成反饋。"
        
        if len(interview_history) < 1:
            return "❌ 面試問答數量不足,無法生成有效反饋。"
        
        # 格式化面試歷史
        history_str = self._format_interview_history(interview_history)
        
        # 構建 prompt
        prompt = self._build_feedback_prompt(job, resume, history_str, lang)
        
        try:
            # 調用 Ollama API
            feedback = await self._call_ollama(prompt)
            return feedback
        except Exception as e:
            print(f"❌ Ollama 生成反饋失敗: {str(e)}")
            return f"無法生成反饋,請稍後再試。錯誤詳情: {str(e)}"
    
    def _format_interview_history(self, history: List[Tuple[str, str]]) -> str:
        """格式化面試歷史為可讀字串"""
        formatted = []
        for i, (question, answer) in enumerate(history, 1):
            formatted.append(f"【第 {i} 題】")
            formatted.append(f"問題: {question}")
            formatted.append(f"回答: {answer}")
            formatted.append("")  # 空行分隔
        return "\n".join(formatted)
    
    def _build_feedback_prompt(
        self,
        job: str,
        resume: str,
        history_str: str,
        lang: str
    ) -> str:
        """構建 LLM 提示詞"""
        
        if lang == "zh":
            prompt = f"""你是一位資深的 {job} 領域面試官,擁有豐富的面試經驗。請根據以下資訊,用繁體中文生成一份專業且具體的面試反饋報告。

【應徵職位】
{job}

【應徵者履歷重點】
{resume}

【面試問答記錄】
{history_str}

【反饋報告要求】
請按照以下結構生成詳細反饋:

1. **整體表現評估** (約 150 字)
   - 概述應徵者在本次面試中的整體表現
   - 指出最突出的 2-3 個強項
   - 指出最需要改善的 2-3 個弱項

2. **逐題分析與建議** (每題約 100 字)
   - 針對每個問題的回答進行具體評價
   - 指出回答的優點(如果有)
   - 指出回答的不足或可改進之處
   - 提供具體的改善建議或參考答案方向

3. **技能與能力評估**
   - 專業技能掌握程度
   - 溝通表達能力
   - 邏輯思維能力
   - 問題解決能力

4. **改善建議** (約 200 字)
   - 提供 3-5 條具體可行的改善建議
   - 建議補充學習的知識領域或技能
   - 推薦相關學習資源或練習方向

5. **綜合評分**
   - 專業能力: X/10 分
   - 溝通表達: X/10 分
   - 邏輯思維: X/10 分
   - 整體評分: X/10 分
   - 錄取建議: [強烈推薦/推薦/保留/不推薦]

請確保反饋內容:
- 具體且有建設性,避免空泛評語
- 基於實際回答內容進行評價
- 語氣專業且友善,鼓勵應徵者持續進步
- 提供可操作的改善方向
"""
        else:  # English
            prompt = f"""You are a senior interviewer in the {job} field with extensive interview experience. Please generate a professional and specific interview feedback report in English based on the following information.

【Target Position】
{job}

【Candidate Resume Highlights】
{resume}

【Interview Q&A Records】
{history_str}

【Feedback Report Requirements】
Please generate detailed feedback following this structure:

1. **Overall Performance Assessment** (~150 words)
   - Summarize the candidate's overall performance
   - Highlight 2-3 key strengths
   - Identify 2-3 areas for improvement

2. **Question-by-Question Analysis** (~100 words each)
   - Evaluate each answer specifically
   - Point out strengths (if any)
   - Identify weaknesses or areas for improvement
   - Provide specific suggestions or reference answer directions

3. **Skills & Abilities Assessment**
   - Technical competence
   - Communication skills
   - Logical thinking
   - Problem-solving abilities

4. **Improvement Recommendations** (~200 words)
   - Provide 3-5 specific and actionable suggestions
   - Recommend knowledge areas or skills to develop
   - Suggest relevant learning resources

5. **Overall Score**
   - Technical Skills: X/10
   - Communication: X/10
   - Logical Thinking: X/10
   - Overall Score: X/10
   - Hiring Recommendation: [Strongly Recommend/Recommend/Hold/Not Recommend]

Ensure the feedback is:
- Specific and constructive
- Based on actual responses
- Professional yet encouraging
- Provides actionable improvement directions
"""
        
        return prompt
    
    async def _call_ollama(self, prompt: str) -> str:
        """調用 Ollama API 生成文本"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 2000
            }
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(self.ollama_url, json=payload)
            response.raise_for_status()
            
            result = response.json()
            return result.get("response", "").strip()
    
    async def generate_quick_summary(
        self,
        interview_history: List[Tuple[str, str]]
    ) -> str:
        """生成簡短的面試摘要(用於即時顯示)"""
        if not interview_history:
            return "尚無面試記錄"
        
        prompt = f"""請用 50 字以內,總結以下面試的核心表現:

{self._format_interview_history(interview_history)}

要求:
- 只用一句話概括
- 重點突出強弱項
- 語氣客觀專業
"""
        
        try:
            return await self._call_ollama(prompt)
        except Exception as e:
            return f"摘要生成失敗: {str(e)}"