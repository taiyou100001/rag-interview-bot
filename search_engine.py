from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.huggingface_api import HuggingFaceInferenceAPI
# from llama_index.llms.huggingface import HuggingFaceLLM
from dotenv import load_dotenv
from pathlib import Path
import os

# 載入環境變數
load_dotenv(dotenv_path=Path(__file__).resolve().parent / "bin" / ".env")
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise ValueError("❌ 找不到 HuggingFace TOKEN，請確認 .env 檔案設定。")

# 設定 LLM
from llama_index.core.settings import Settings
Settings.llm = HuggingFaceInferenceAPI(
    model_name="HuggingFaceH4/zephyr-7b-beta",
    tokenizer_name="HuggingFaceH4/zephyr-7b-beta",
    api_key=TOKEN
)

def build_search_index(data_dir="data"):
    # 檢查資料目錄是否存在
    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"❌ 資料目錄 {data_dir} 不存在。")
    
    embed_model = HuggingFaceEmbedding(
        model_name="nomic-ai/nomic-embed-text-v1",
        trust_remote_code=True
    )
    # 明確指定 JSON 文件
    documents = SimpleDirectoryReader(
        input_dir=data_dir,
        required_exts=[".json"],
        recursive=True
    ).load_data()
    
    if not documents:
        raise ValueError(f"❌ {data_dir} 中未找到有效的 JSON 文件。")
        
    index = VectorStoreIndex.from_documents(documents, embed_model=embed_model)
    return index

def query_job_knowledge(index, query):
    query_engine = index.as_query_engine(llm=Settings.llm)
    try:
        response = query_engine.query(query)
        return response
    except Exception as e:
        raise Exception(f"❌ 查詢失敗：{str(e)}")

if __name__ == "__main__":
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    try:
        index = build_search_index()
        question = input("請輸入要查詢的職位關鍵字或問題（例如：行銷面試技巧）：")
        result = query_job_knowledge(index, question)
        print("\n📚 找到相關資料：\n")
        print(result.response)
    except Exception as e:
        print(f"❌ 錯誤：{str(e)}")