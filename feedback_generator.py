# feedback_generator.py
from huggingface_hub import InferenceClient
from utils import get_hf_token

# 初始化 Hugging Face LLM
TOKEN = get_hf_token()
client = InferenceClient(provider="fireworks-ai", token=TOKEN)

def generate_feedback(job, resume, interview_history, lang="zh"):
    """
    根據職位、履歷和面試問答歷史，使用 LLM 生成專業反饋。

    Args:
        job (str): 應徵職位名稱
        resume (str): 履歷重點
        interview_history (list): 包含 (問題, 回答) 元組的列表
        lang (str): 反饋語言，預設為繁體中文 ('zh')

    Returns:
        str: 格式化的反饋報告，或錯誤訊息
    """
    if not interview_history or not isinstance(interview_history, list):
        return "❌ 無有效的面試歷史記錄，無法生成反饋。"

    # 格式化面試歷史
    history_str = "\n".join([f"問題：{q}\n回答：{a}" for q, a in interview_history])
    
    prompt = f"""
    你是一位資深軟體工程師面試官，請根據以下職位、履歷重點和面試問答歷史，用{lang}生成專業的反饋報告。
    反饋應包括：
    1. 整體表現評估（強項與弱項）
    2. 針對每個回答的具體建議
    3. 改善建議
    4. 最終評分（滿分10分）

    職位：{job}
    履歷重點：{resume}
    面試問答歷史：
    {history_str}
    """

    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1500  # 確保反饋內容足夠詳細
        )
        feedback = response.choices[0].message.content.strip()
        return feedback
    except Exception as e:
        print(f"❌ LLM 生成反饋失敗：{str(e)}")
        return "無法生成反饋，請稍後再試。"