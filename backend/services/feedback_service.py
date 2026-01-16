# backend/services/feedback_service.py
from typing import List, Dict
from dataclasses import dataclass
from ollama import Client
import json

@dataclass
class FeedbackResult:
    """回饋結果結構"""
    overall_score: float  # 0-100
    dimensions: Dict[str, float]  # 各維度分數
    strengths: List[str]  # 優點
    improvements: List[str]  # 改進建議
    summary: str  # 總結文字

class FeedbackService:
    """面試回饋生成服務"""
    
    def __init__(self):
        self.client = Client()
        self.model = 'llama3.1:8b'
    
    def analyze_interview(
        self, 
        job_title: str, 
        history: List[Dict],
        resume_text: str = ""
    ) -> FeedbackResult:
        """分析面試表現並生成結構化回饋
        
        Args:
            job_title: 職位名稱
            history: 對話歷史
            resume_text: 履歷內容(用於比對一致性)
        
        Returns:
            FeedbackResult 結構化回饋
        """
        # 準備對話摘要
        qa_summary = self._prepare_summary(history)
        
        # LLM評估提示詞
        prompt = f"""你是專業的面試評估顧問,請針對以下面試進行評估:

**職位**: {job_title}
**面試輪數**: {len(history)}

**對話紀錄**:
{qa_summary}

**評估任務**:
請從以下5個維度評分(0-100),並給出建議:

1. **表達能力**(Communication): 回答是否清晰、有條理、避免冗長
2. **專業知識**(Expertise): 是否展現職位相關的技能與經驗
3. **問題理解**(Comprehension): 是否準確理解問題並切中要點
4. **自信態度**(Confidence): 語氣是否穩定、避免過度不確定用詞
5. **發展潛力**(Potential): 是否展現學習意願與成長空間

**輸出格式**(務必回傳有效JSON):
{{
  "overall_score": 75.5,
  "dimensions": {{
    "communication": 80,
    "expertise": 70,
    "comprehension": 75,
    "confidence": 72,
    "potential": 78
  }},
  "strengths": ["優點1", "優點2", "優點3"],
  "improvements": ["建議1", "建議2", "建議3"],
  "summary": "整體表現總結,控制在150字內"
}}

請只輸出JSON,無其他內容。"""

        try:
            response = self.client.chat(
                model=self.model,
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.3, 'num_predict': 500}
            )
            
            # 解析回應
            content = response['message']['content'].strip()
            
            # 清理可能的markdown標記
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            data = json.loads(content)
            
            return FeedbackResult(
                overall_score=float(data.get('overall_score', 70)),
                dimensions=data.get('dimensions', {}),
                strengths=data.get('strengths', []),
                improvements=data.get('improvements', []),
                summary=data.get('summary', '面試表現穩定,建議持續精進。')
            )
            
        except Exception as e:
            print(f"[ERROR] 回饋生成失敗: {e}")
            # 回傳預設回饋
            return FeedbackResult(
                overall_score=70.0,
                dimensions={
                    "communication": 70,
                    "expertise": 70,
                    "comprehension": 70,
                    "confidence": 70,
                    "potential": 70
                },
                strengths=["展現基本專業知識", "保持穩定回答態度"],
                improvements=["可增加具體案例說明", "強化技術細節描述"],
                summary="整體表現中規中矩,建議多準備實際案例以增強說服力。"
            )
    
    def _prepare_summary(self, history: List[Dict], max_pairs: int = 10) -> str:
        """準備對話摘要(避免超出token限制)"""
        limited_history = history[-max_pairs:] if len(history) > max_pairs else history
        
        qa_texts = []
        for i, qa in enumerate(limited_history, 1):
            question = qa.get('question', '')[:100]  # 限制長度
            answer = qa.get('answer', '')[:200]
            qa_texts.append(f"【第{i}題】\nQ: {question}\nA: {answer}\n")
        
        return "\n".join(qa_texts)


# 全局實例
feedback_service = FeedbackService()