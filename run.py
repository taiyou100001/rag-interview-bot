# run.py
import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()  # 自動載入 .env

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,        # 開發時熱重載
        log_level="info"
    )