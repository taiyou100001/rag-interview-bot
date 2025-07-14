from llama_index.core import SimpleDirectoryReader
import os
import json
import random
from huggingface_hub import InferenceClient
from dotenv import load_dotenv
from pathlib import Path

# 讀取 TOKEN
load_dotenv(dotenv_path=Path(__file__).resolve().parent / "bin" / ".env")
TOKEN = os.environ.get("TOKEN")
client = InferenceClient(provider="fireworks-ai", api_key=TOKEN)

def load_questions(data_dir="data"):
    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"❌ 資料夾 {data_dir} 不存在")

    documents = SimpleDirectoryReader(
        input_dir=data_dir,
        required_exts=[".json"],
        recursive=True
    ).load_data()

    if not documents:
        raise ValueError(f"❌ 找不到有效 JSON 文件")

    all_questions = []
    for doc in documents:
        try:
            questions = json.loads(doc.text)
            all_questions.extend(questions)
        except json.JSONDecodeError as e:
            print(f"❌ 解析錯誤：{e}")
    return all_questions

def ask_next_question(questions, previous_answer=None, previous_question=None):
    if previous_answer and previous_question:
        prompt = f"""你是一個面試官，根據以下問題和回答，生成一個繁體中文、簡潔（20字以內）、與面試相關的完整問句，避免陳述句。
問題：{previous_question}
回答：{previous_answer}"""
        try:
            completion = client.chat.completions.create(
                model="meta-llama/Llama-3.3-70B-Instruct",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ 生成追問失敗：{str(e)}，改用題庫")
    
    return random.choice(questions)["題目"]
