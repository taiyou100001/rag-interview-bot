# question_generator.py
from huggingface_hub import InferenceClient
from utils import get_hf_token
import random

# 初始化 Hugging Face LLM
TOKEN = get_hf_token()
client = InferenceClient(provider="fireworks-ai", token=TOKEN)

# 避免重複提問
asked_history = set()

def generate_question(job, resume, lang="zh"):
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
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ LLM 生成問題失敗：{str(e)}")
        return "無法生成問題，請稍後再試。"

def ask_next_question(questions, prev_q=None, prev_a=None):
    if prev_q and prev_a:
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
            return new_question
        except Exception as e:
            print(f"❌ LLM 追問失敗：{str(e)}")

    # 從資料集中挑選未問過的問題
    unused = [q for q in questions if q["題目"] not in asked_history]
    if not unused:
        asked_history.clear()
        unused = questions
    selected = random.choice(unused)
    asked_history.add(selected["題目"])
    return selected["題目"]
