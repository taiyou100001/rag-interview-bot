# backend/services/feedback_service.py
from typing import List, Dict, Tuple
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


# 判定「無效回答」的標記字串（與 interview_router.py 一致）
_INVALID_ANSWER_MARKERS = [
    "（使用者語音要求跳過",
    "[使用者按鈕跳過]",
    "（STT 無法辨識）",
]


def _classify_answer(answer: str) -> str:
    """
    分類回答品質：
    - "empty"   : 完全沒有回答（空字串）
    - "skipped" : 使用者主動跳過
    - "short"   : 回答過短（< 10 字），幾乎沒有內容
    - "valid"   : 正常回答
    """
    if not answer or not answer.strip():
        return "empty"
    for marker in _INVALID_ANSWER_MARKERS:
        if marker in answer:
            return "skipped"
    if len(answer.strip()) < 10:
        return "short"
    return "valid"


def _compute_answer_stats(history: List[Dict]) -> Dict:
    """
    統計各類型回答數量，供 prompt 與分數懲罰使用。
    回傳：
    {
        "total": int,
        "valid": int,
        "empty": int,
        "skipped": int,
        "short": int,
        "valid_ratio": float  # 0.0 ~ 1.0
    }
    """
    counts = {"total": len(history), "valid": 0, "empty": 0, "skipped": 0, "short": 0}
    for qa in history:
        kind = _classify_answer(qa.get("answer", ""))
        counts[kind] += 1
    counts["valid_ratio"] = counts["valid"] / counts["total"] if counts["total"] > 0 else 0.0
    return counts


class FeedbackService:
    """面試回饋生成服務"""

    def __init__(self):
        self.client = Client()
        self.model = "llama3.1:8b"

    def analyze_interview(
        self,
        job_title: str,
        history: List[Dict],
        resume_text: str = "",
    ) -> FeedbackResult:
        """
        分析面試表現並生成結構化回饋。

        主要改進：
        1. 在 prompt 中明確標記每題的回答品質（空白/跳過/過短/正常）。
        2. 要求 LLM 對無效回答給出嚴格懲罰分數。
        3. 在 LLM 回傳結果後，再以「有效回答比例」做最終分數上限修正，
           防止 LLM 寬鬆評分。
        4. fallback 分數改為與有效回答比例掛鉤，不再固定給 70 分。
        """
        stats = _compute_answer_stats(history)
        qa_summary = self._prepare_summary(history)

        prompt = f"""你是嚴格且公正的面試評估顧問，請針對以下面試進行評估。

**職位**: {job_title}
**面試輪數**: {stats['total']}
**有效回答數**: {stats['valid']} / {stats['total']}（空白={stats['empty']}, 跳過={stats['skipped']}, 過短={stats['short']}）

**對話紀錄**（每題已標示回答品質）:
{qa_summary}

**評分規則（非常重要，必須嚴格遵守）**:
- 若某題回答為「[空白/無回應]」，該題視為 0 分，並大幅拉低整體分數。
- 若某題回答為「[跳過]」，視為放棄，扣分幅度僅略輕於空白。
- 若某題回答「[過短]」（不足 10 字），視為回答不足，適度扣分。
- 有效回答比例不足 50% 時，overall_score 不得超過 40 分。
- 有效回答比例不足 30% 時，overall_score 不得超過 25 分。
- 完全沒有任何有效回答時，overall_score 必須為 0。

**評估維度（各 0-100 分）**:
1. **表達能力** (communication): 回答是否清晰、有條理
2. **專業知識** (expertise): 是否展現職位相關技能與經驗
3. **問題理解** (comprehension): 是否準確理解問題並切中要點
4. **自信態度** (confidence): 語氣是否穩定
5. **發展潛力** (potential): 是否展現學習意願與成長空間

**輸出格式（只輸出有效 JSON，不要有其他文字）**:
{{
  "overall_score": 0,
  "dimensions": {{
    "communication": 0,
    "expertise": 0,
    "comprehension": 0,
    "confidence": 0,
    "potential": 0
  }},
  "strengths": ["優點1（若無有效回答可填「無足夠資訊評估」）"],
  "improvements": ["改進建議1", "改進建議2"],
  "summary": "整體表現總結，控制在150字內，必須誠實反映無效回答的狀況"
}}"""

        try:
            response = self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.2, "num_predict": 600},
            )

            content = response["message"]["content"].strip()

            # 清理 markdown 標記
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content)

            # --- 分數上限強制修正（防止 LLM 過於寬鬆）---
            llm_score = float(data.get("overall_score", 0))
            capped_score = self._apply_score_cap(llm_score, stats)

            # 同步修正各維度分數（等比例縮減）
            dimensions = data.get("dimensions", {})
            if llm_score > 0 and capped_score < llm_score:
                scale = capped_score / llm_score
                dimensions = {k: round(v * scale, 1) for k, v in dimensions.items()}

            return FeedbackResult(
                overall_score=capped_score,
                dimensions=dimensions,
                strengths=data.get("strengths", []),
                improvements=data.get("improvements", []),
                summary=data.get("summary", ""),
            )

        except Exception as e:
            print(f"[ERROR] 回饋生成失敗: {e}")
            return self._fallback_result(stats)

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    def _apply_score_cap(self, raw_score: float, stats: Dict) -> float:
        """
        根據有效回答比例對分數設上限，防止 LLM 評分過於寬鬆。
        """
        valid_ratio = stats["valid_ratio"]

        if valid_ratio == 0.0:
            return 0.0
        if valid_ratio < 0.3:
            cap = 25.0
        elif valid_ratio < 0.5:
            cap = 40.0
        elif valid_ratio < 0.7:
            cap = 65.0
        else:
            cap = 100.0  # 有效回答 >= 70%，不限制上限

        return round(min(raw_score, cap), 1)

    def _prepare_summary(self, history: List[Dict], max_pairs: int = 10) -> str:
        """
        準備對話摘要，每題明確標示回答品質，讓 LLM 清楚知道哪些題目沒有回答。
        """
        limited_history = history[-max_pairs:] if len(history) > max_pairs else history

        qa_texts = []
        for i, qa in enumerate(limited_history, 1):
            question = qa.get("question", "")[:100]
            answer = qa.get("answer", "")
            kind = _classify_answer(answer)

            if kind == "empty":
                answer_display = "【⚠️ 空白/無回應】"
            elif kind == "skipped":
                answer_display = "【⚠️ 跳過此題】"
            elif kind == "short":
                answer_display = f"【⚠️ 回答過短】{answer.strip()}"
            else:
                answer_display = answer[:200]

            qa_texts.append(f"【第{i}題】\nQ: {question}\nA: {answer_display}\n")

        return "\n".join(qa_texts)

    def _fallback_result(self, stats: Dict) -> FeedbackResult:
        """
        LLM 失敗時的 fallback，分數根據有效回答比例計算，不再固定給 70。
        """
        valid_ratio = stats["valid_ratio"]
        base_score = round(valid_ratio * 60, 1)  # 最高 60 分（fallback 保守估計）

        if valid_ratio == 0:
            strengths = ["無法評估，本次面試沒有任何有效回答"]
            improvements = ["請在面試中開口回答問題", "可以先從簡短的自我介紹開始練習"]
            summary = "本次面試未偵測到任何有效回答，無法進行評估。請重新進行面試並嘗試回答每一題。"
        elif valid_ratio < 0.5:
            strengths = ["有嘗試回答部分問題"]
            improvements = ["請盡量回答每一道題目", "避免跳過問題，即使不確定也可以分享想法"]
            summary = f"本次面試有效回答比例偏低（{stats['valid']}/{stats['total']} 題），建議多加練習並嘗試完整作答。"
        else:
            strengths = ["能夠回答大部分問題"]
            improvements = ["可增加具體案例說明", "強化技術細節描述"]
            summary = "整體表現尚可，建議多準備實際案例以增強說服力。"

        dim_score = base_score
        return FeedbackResult(
            overall_score=base_score,
            dimensions={
                "communication": dim_score,
                "expertise": dim_score,
                "comprehension": dim_score,
                "confidence": dim_score,
                "potential": dim_score,
            },
            strengths=strengths,
            improvements=improvements,
            summary=summary,
        )


# 全局實例
feedback_service = FeedbackService()