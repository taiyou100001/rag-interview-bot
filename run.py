# run.py  ← 直接覆蓋成這版，之後永遠一鍵開瀏覽器
import uvicorn
import webbrowser
import threading
import time

def open_browser():
    time.sleep(1)
    webbrowser.open("http://127.0.0.1:8000/docs")

if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )