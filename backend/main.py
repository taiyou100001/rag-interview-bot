# backend/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

from backend.api import resume_router, interview_router, audio_router
from backend.database import init_db

# backend/main.py 加上這兩行
from backend.utils.file_helper import ensure_dirs
ensure_dirs()  # 程式啟動時自動建立 uploads/ 與 static/audio/

app = FastAPI(title="VR Interview System Backend")

# 初始化
init_db()

# 路由
app.include_router(resume_router, prefix="/api")
app.include_router(interview_router, prefix="/api")
app.include_router(audio_router)

# 靜態檔案
os.makedirs("static/audio", exist_ok=True)
app.mount("/audio", StaticFiles(directory="static/audio"), name="audio")