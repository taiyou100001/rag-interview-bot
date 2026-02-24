# scripts/test_feedback.py
"""測試反饋生成功能"""
import asyncio
import sys
from pathlib import Path

# 添加專案根目錄到 Python 路徑
sys.path.append(str(Path(__file__).parent.parent))

from backend.services.feedback_service import FeedbackService


async def test_feedback_generation():
    """測試反饋生成"""
    
    # 模擬面試資料
    job = "後端工程師"
    resume = "熟悉 Python、FastAPI、資料庫設計,有 2 年開發經驗"
    
    interview_history = [
        ("請說明 FastAPI 和 Flask 的主要差異?", 
         "FastAPI 使用了 Pydantic 進行資料驗證,而且支援非同步處理,速度比較快。Flask 則比較簡單易學。"),
        
        ("你如何設計一個高併發的 RESTful API?",
         "我會使用非同步框架,加入快取機制,還有資料庫連線池來提升效能。"),
        
        ("說明你處理過最複雜的技術問題",
         "之前遇到資料庫查詢很慢的問題,後來加了索引和優化 SQL 就解決了。")
    ]
    
    print("=" * 60)
    print("🧪 測試 AI 反饋生成功能")
    print("=" * 60)
    print(f"\n職位: {job}")
    print(f"履歷: {resume}")
    print(f"\n面試題數: {len(interview_history)}\n")
    
    # 初始化服務
    service = FeedbackService()
    
    print("⏳ 正在生成反饋報告...\n")
    
    # 生成反饋
    feedback = await service.generate_feedback(
        job=job,
        resume=resume,
        interview_history=interview_history,
        lang="zh"
    )
    
    print("=" * 60)
    print("📊 生成的反饋報告")
    print("=" * 60)
    print(feedback)
    print("\n")
    
    # 測試快速摘要
    print("=" * 60)
    print("⚡ 測試快速摘要功能")
    print("=" * 60)
    
    summary = await service.generate_quick_summary(interview_history)
    print(f"\n摘要: {summary}\n")


if __name__ == "__main__":
    # 確保 Ollama 服務正在運行
    print("⚠️  請確保 Ollama 服務已啟動: ollama serve")
    print("⚠️  請確保已下載模型: ollama pull llama3.1:8b\n")
    
    asyncio.run(test_feedback_generation())