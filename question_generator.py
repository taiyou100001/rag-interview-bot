# question_generator.py
from huggingface_hub import InferenceClient
from utils import get_hf_token
import random

# 初始化 Hugging Face LLM
TOKEN = get_hf_token()
client = InferenceClient(provider="fireworks-ai", token=TOKEN)

# 避免重複提問
asked_history = set()
used_types = set()

# 控制追問次數
MAX_FOLLOWUP = 1
followup_count = 0

# def extract_topic(text):
#     """
#     嘗試從問題中抽取主題（簡化版：取出前三個中文字或關鍵詞）
#     可改成 NLP 模型輔助
#     """
#     match = re.findall(r"[一-龥]{2,}", text)
#     return match[0] if match else text[:4]

def generate_question(job, resume, lang="zh"):

    followup_count = 0
    asked_history.clear()
    used_types.clear()

    prompt = f"""
        你是一位面試官，請根據以下職位與履歷重點，用{lang}生成一個有深度的面試問題，避免陳述句。\n"
        職位：{job}\n"
        履歷重點：{resume}"""

    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        question = response.choices[0].message.content.strip()
        asked_history.add(question)
        # used_type.add(extract_topic(question))
        return question
    except Exception as e:
        print(f"❌ LLM 生成問題失敗：{str(e)}")
        return "無法生成問題，請稍後再試。"

def ask_next_question(questions, prev_q=None, prev_a=None):
    global followup_count, asked_history, used_types

    # 如果還沒達到最大追問次數，嘗試用 LLM 追問
    if prev_q and prev_a and followup_count < MAX_FOLLOWUP:
        prompt = f"""
            你是一位資深面試官，根據下面的問題與回答，提出一個有深度的追問，用繁體中文提出新問題，避免陳述句。\n"
            問題：{prev_q}\n"
            回答：{prev_a}"""
        
        try:
            response = client.chat.completions.create(
                model="meta-llama/Llama-3.3-70B-Instruct",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            new_question = response.choices[0].message.content.strip()
            
            if new_question in asked_history:
                raise ValueError("⚠️ 問題重複，將使用資料集內隨機提問。")
            
            asked_history.add(new_question)
            # topic_history.add(extract_topic(new_question))
            followup_count += 1
            return new_question
        except Exception as e:
            print(f"❌ LLM 追問失敗：{str(e)}")

    # 超過追問次數或 LLM 失敗後：切換新主題，從資料集中挑選未問過的問題
    followup_count = 0

    # 防呆：questions 為空或非 list
    if not questions or not isinstance(questions, list):
        raise ValueError("❌ 資料集格式錯誤：questions 必須是 list。")
    
    # 從資料集中挑選：未問過題目 + 類型未重複
    unused = [q for q in questions if isinstance(q, dict)
              and "題目" in q and "類型" in q
              and q["題目"] not in asked_history
              and q["類型"] not in used_types]
    # unused = [q for q in questions 
    #           if q["題目"] not in asked_history 
    #           and extract_topic(q["題目"]) not in topic_history]
    
    # 若所有類型都已用過，就重置 used_types
    if not unused:
        used_types.clear()
        unused = [q for q in questions if isinstance(q, dict) and "題目" in q and q["題目"] not in asked_history]

    # 若所有題目都問完了，就完全重置
    if not unused:
        asked_history.clear()
        used_types.clear()
        unused = [q for q in questions if isinstance(q, dict) and "題目" in q]

    # 最終檢查
    if not unused:
        raise ValueError("❌ 沒有可用的題目可問。請確認題庫格式。")
    
    selected = random.choice(unused)

    # 多一層防呆：確認 selected 有 "題目"
    if not isinstance(selected, dict) or "題目" not in selected:
        raise ValueError(f"❌ 選到無效題目格式：{selected}")
    
    asked_history.add(selected["題目"])
    used_types.add(selected.get("類型", "未分類"))  # 若無類型則標記為未分類
    return selected["題目"]
