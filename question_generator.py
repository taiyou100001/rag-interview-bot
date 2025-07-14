from huggingface_hub import InferenceClient
from dotenv import load_dotenv
from pathlib import Path
import os

# 讀取 TOKEN
load_dotenv(dotenv_path=Path(__file__).resolve().parent / "bin" / ".env")
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise ValueError("❌ 找不到 HuggingFace TOKEN，請確認 .env 檔案設定。")

client = InferenceClient(provider="fireworks-ai", api_key=TOKEN)

def generate_question(job_title, resume_summary, lang="zh"):
    prompt = f"""你是一位專業面試官，應徵職位是「{job_title}」。
以下是履歷摘要：
{resume_summary}
請用{lang}提出一個有深度的面試問題（20字以內）："""

    try:
        completion = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ 產生第一題失敗，使用備用問題：{str(e)}")
        return "請介紹你自己。"
