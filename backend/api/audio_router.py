# backend/api/audio_router.py
from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI

router = APIRouter()
# 靜態檔案由 main.py mount，不需要在這裡 mount