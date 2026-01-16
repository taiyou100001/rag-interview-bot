# run.py - Windows 相容版本
import uvicorn
import webbrowser
import time
import sys
import os

def open_browser():
    """延遲開啟瀏覽器"""
    time.sleep(2)  # 等待伺服器啟動
    try:
        url = "http://127.0.0.1:8000/docs"
        print(f"\n{'='*60}")
        print(f"🚀 正在開啟瀏覽器: {url}")
        print(f"{'='*60}\n")
        webbrowser.open(url)
    except Exception as e:
        print(f"⚠️  無法自動開啟瀏覽器: {e}")
        print(f"請手動開啟: http://127.0.0.1:8000/docs")

if __name__ == "__main__":
    # 檢查是否為主進程 (避免在 reload worker 中重複開啟)
    if os.environ.get("RUN_MAIN") != "true":
        # 設定環境變數標記
        os.environ["RUN_MAIN"] = "true"
        
        # 使用 subprocess 避免 threading 問題
        import subprocess
        import threading
        
        # 啟動瀏覽器的線程
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()
    
    # 啟動 uvicorn
    try:
        uvicorn.run(
            "backend.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n\n👋 伺服器已停止")
        sys.exit(0)