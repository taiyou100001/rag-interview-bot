# search_engine.py
from llama_index.core import SimpleDirectoryReader
import os
import json

def load_questions(data_dir="data"):
    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"❌ 資料夾不存在：{data_dir}")

    documents = SimpleDirectoryReader(
        input_dir=data_dir,
        required_exts=[".json"],
        recursive=True
    ).load_data()

    if not documents:
        raise ValueError("❌ 沒有找到任何可用的資料文件。")

    all_questions = []
    for doc in documents:
        try:
            questions = json.loads(doc.text)
            if not isinstance(questions, list):
                print(f"⚠️ 資料格式錯誤於 {doc.metadata['file_path']}：⚠️ JSON 格式錯誤：不是 list。")
                continue
            all_questions.extend(questions)
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON 解析錯誤於 {doc.metadata['file_path']}：{e}")
    
    if not all_questions:
        raise ValueError("❌ 沒有有效的面試問題可用。")

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
