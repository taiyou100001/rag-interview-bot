from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
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
client = InferenceClient(api_key=TOKEN)  # 若使用第三方提供者，添加 provider="featherless-ai"

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
            all_questions.extend(questions)
        except json.JSONDecodeError as e:
            print(f"❌ JSON 解析錯誤於檔案 {doc.metadata['file_path']}：{str(e)}")
            continue
    
    if not all_questions:
        raise ValueError("❌ 無有效問題數據。")
    
    return all_questions

def ask_next_question(questions, previous_answer=None, previous_question=None):
    if previous_answer and previous_question:
        prompt = f"根據以下問題和回答，生成一個相關的面試問題（自然語言）:\n問題: {previous_question}\n回答: {previous_answer}"
        try:
            completion = client.chat.completions.create(
                model="HuggingFaceH4/zephyr-7b-beta",
                messages=[{"role": "user", "content": prompt}]
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ LLM 查詢失敗：{str(e)}")
            return random.choice(questions)["題目"]
    
    return random.choice(questions)["題目"]

if __name__ == "__main__":
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    try:
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