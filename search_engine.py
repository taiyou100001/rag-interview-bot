from llama_index.core import SimpleDirectoryReader
from huggingface_hub import InferenceClient
from dotenv import load_dotenv
from pathlib import Path
import os
import random
import json

# 載入環境變數
load_dotenv(dotenv_path=Path(__file__).resolve().parent / "bin" / ".env")
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise ValueError("❌ 找不到 HuggingFace TOKEN，請確認 .env 檔案設定。")

# 設定 InferenceClient
client = InferenceClient(provider="fireworks-ai", api_key=TOKEN)

def load_questions(data_dir="data"):
    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"❌ 資料目錄 {data_dir} 不存在。")
    
    documents = SimpleDirectoryReader(
        input_dir=data_dir,
        required_exts=[".json"],
        recursive=True
    ).load_data()
    
    if not documents:
        raise ValueError(f"❌ {data_dir} 中未找到有效的 JSON 文件。")
    
    all_questions = []
    for doc in documents:
        try:
            questions = json.loads(doc.text)
            if not isinstance(questions, list):
                print(f"⚠️ 資料格式錯誤於 {doc.metadata['file_path']}：⚠️ JSON 格式錯誤：不是 list。")
                continue
            all_questions.extend(questions)
        except json.JSONDecodeError as e:
            print(f"❌ JSON 解析錯誤於檔案 {doc.metadata['file_path']}：{str(e)}")
            continue
    
    if not all_questions:
        raise ValueError("❌ 無有效問題數據。")
    
    return all_questions

def load_filtered_questions(job_title):
    """
    根據職位名稱過濾資料集內的問題。若無符合職位，則回傳全部題目。
    """
    all_questions = load_questions()
    filtered = [q for q in all_questions if q.get("職位", "") in job_title]

    if not filtered:
        print(f"⚠️ 沒有找到與『{job_title}』相關的題目，將使用所有題目。")
        return all_questions
    return filtered

def ask_next_question(questions, previous_answer=None, previous_question=None):
    if previous_answer and previous_question:
        prompt = f"你是一個面試官，根據以下問題和回答，生成一個繁體中文、簡潔（20字以內）、與面試相關的完整問句，避免陳述句或冗長回應。例如：'如何處理工作壓力？'：\n問題: {previous_question}\n回答: {previous_answer}"
        try:
            completion = client.chat.completions.create(
                model="meta-llama/Llama-3.3-70B-Instruct",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ LLM 查詢失敗：{str(e)}")
            return random.choice(questions)["題目"]
    
    return random.choice(questions)["題目"]

if __name__ == "__main__":
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    try:
        # Example: Filter questions for a specific job title
        job_title = input("請輸入職位名稱（留空則使用所有題目）：")
        if job_title:
            questions = load_filtered_questions(job_title)
        else:
            questions = load_questions()
        
        previous_answer = None
        previous_question = None
        
        while True:
            question = ask_next_question(questions, previous_answer, previous_question)
            print(f"\n📝 問題：{question}")
            answer = input("你的回答（輸入 '退出' 結束）：")
            if answer.lower() == "退出":
                print("結束面試練習。")
                break
            
            previous_question = question
            previous_answer = answer
            
    except Exception as e:
        print(f"❌ 錯誤：{str(e)}")