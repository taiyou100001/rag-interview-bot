# main.py

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings
from backend.api import resume_router, interview_router

app = FastAPI(title=settings.PROJECT_NAME)

# --- CORS 設定 (允許 Unity 連線) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 開發階段允許所有來源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 掛載靜態檔案 (讓 Unity 可以下載 MP3) ---
# 網址格式: http://IP:8000/static/audio/xxx.wav
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- 註冊路由 ---
app.include_router(resume_router.router, prefix="/api/v1/resume", tags=["resume"])
app.include_router(interview_router.router, prefix="/api/v1/interview", tags=["interview"])

@app.get("/")
def root():
    return {"message": "VR Interview Bot API is running!"}

if __name__ == "__main__":
    # 使用 0.0.0.0 讓區網內的其他裝置 (Unity) 可以連線
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
