# main.py

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings
from backend.api import resume_router, interview_router

app = FastAPI(title=settings.PROJECT_NAME)

# --- CORS 設定 ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 註冊路由 ---
app.include_router(resume_router.router, prefix="/api/v1/resume", tags=["resume"])
app.include_router(interview_router.router, prefix="/api/v1/interview", tags=["interview"])
# 注意：移除了 static mount 和 audio_router

@app.get("/")
def root():
    return {"message": "VR Interview Bot API is running!"}

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
    