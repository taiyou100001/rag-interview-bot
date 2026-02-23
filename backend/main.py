# main.py

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings
from backend.api import resume_router, interview_router
from backend.database import init_db

app = FastAPI(title=settings.PROJECT_NAME, description="沉浸式智慧模擬面試訓練平台後端服務")

# --- 資料庫初始化 ---
# 確保所有資料表自動建立
init_db()

# --- CORS 設定 ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 註冊路由 ---
app.include_router(resume_router.router, prefix="/api/v1/resume", tags=["履歷功能"])
app.include_router(interview_router.router, prefix="/api/v1/interview", tags=["面試功能"])
# 注意：移除了 static mount 和 audio_router

@app.get("/", tags=["系統"])
def root():
    return {"message": "VR Interview Bot backend is running."}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)