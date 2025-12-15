# backend/config.py
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Literal

class Settings(BaseSettings):
    ENV: Literal["development", "production"] = "development"
    
    # Azure
    AZURE_SUBSCRIPTION_KEY: str
    AZURE_ENDPOINT: str
    AZURE_SPEECH_KEY: str        # ← 修正拼寫！之前寫成 AZZURE
    AZURE_SPEECH_REGION: str = "eastasia"
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///app.db"
    
    # Paths
    UPLOAD_FOLDER: str = "uploads"
    AUDIO_FOLDER: str = "static/audio"

    class Config:
        # 正確路徑：從 config.py 往上 1 層就是專案根目錄
        env_file = str(Path(__file__).resolve().parent.parent / ".env")
        env_file_encoding = "utf-8"

# 除錯用
print("正在載入 .env 檔案...")
env_path = Path(__file__).resolve().parent.parent / ".env"
# print("完整路徑:", env_path)
print("檔案是否存在:", env_path.exists())
if env_path.exists():
    print("檔案內容前3行:")
    print("".join(open(env_path, encoding="utf-8").readlines()[:3]))
else:
    print("警告: .env 不存在！請確認檔名是 .env（不是 .env.txt）")

settings = Settings()
print("設定載入成功！")
print(f"AZURE_SUBSCRIPTION_KEY: {settings.AZURE_SUBSCRIPTION_KEY[:6]}...")