# RAG, 根據職業名稱查找資料
from llama_index.core.settings import Settings # 全域設定
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import os

Settings.llm = None # 強制關掉全域的 LLM 模型

def build_search_index(data_dir="data"):
    embed_model = HuggingFaceEmbedding(
        model_name="nomic-ai/nomic-embed-text-v1",
        trust_remote_code=True
    )
    documents = SimpleDirectoryReader(data_dir).load_data()
    index = VectorStoreIndex.from_documents(documents, embed_model=embed_model)
    return index

def query_job_knowledge(index, query):
    query_engine = index.as_query_engine(llm=None)#"gpt-3.5-turbo", response_mode="tree_summarize")
    response = query_engine.query(query)
    return response

if __name__ == "__main__":
    os.environ["TOKENIZERS_PARALLELISM"] = "false"  # 避免 warning
    index = build_search_index()
    question = input("請輸入要查詢的職位關鍵字或問題（例如：行銷面試技巧）：")
    result = query_job_knowledge(index, question)
    print("\n📚 找到相關資料：\n")
    print(result.response)
