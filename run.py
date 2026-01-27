# run.py - 帶健康檢查版本
import uvicorn
import webbrowser
import time
import sys
import os
import requests

def wait_for_server(url="http://localhost:8000/docs", timeout=30):
    """等待伺服器就緒"""
    print(f"\n等待伺服器啟動...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                print(f"伺服器已就緒！")
                return True
        except requests.exceptions.RequestException:
            time.sleep(0.5)
    
    print(f"等待超時，但仍嘗試開啟瀏覽器...")
    return False

def open_browser():
    """等待伺服器就緒後開啟瀏覽器"""
    time.sleep(3)  # 初始等待
    
    # 健康檢查
    wait_for_server()
    
    try:
        url = "http://localhost:8000/docs"
        print(f"\n{'='*60}")
        print(f"正在開啟瀏覽器: {url}")
        print(f"{'='*60}\n")
        webbrowser.open(url)
    except Exception as e:
        print(f"無法自動開啟瀏覽器: {e}")
        print(f"請手動開啟: http://localhost:8000/docs")

if __name__ == "__main__":
    # 檢查是否為主進程
    if os.environ.get("RUN_MAIN") != "true":
        os.environ["RUN_MAIN"] = "true"
        
        import threading
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
        print("\n\n伺服器已停止")
        sys.exit(0)