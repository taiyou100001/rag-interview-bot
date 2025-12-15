# config.py

import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "VR Interview Bot"
    API_V1_STR: str = "/api/v1"
    
    # --- Azure 設定 (必須與 .env 內的變數名稱完全一致) ---
    AZURE_SUBSCRIPTION_KEY: str
    AZURE_ENDPOINT: str
    AZURE_SPEECH_KEY: str      # 對應 .env 的語音金鑰
    AZURE_SPEECH_REGION: str   # 對應 .env 的語音區域 (如 southeastasia)
    
    # --- 路徑設定 ---
    # __file__ 是 backend/config.py
    # 第一個 dirname 是 backend/
    # 第二個 dirname 是 專案根目錄/
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    UPLOAD_DIR: str = os.path.join(BASE_DIR, "uploads")
    AUDIO_DIR: str = os.path.join(BASE_DIR, "static", "audio")

    class Config:
        # 指定讀取 .env 檔案
        # 注意：請務必在「專案根目錄」執行啟動指令 (uv run backend/main.py)
        # 這樣程式才找得到根目錄下的 .env
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # 忽略 .env 裡多餘的變數，避免報錯

# 初始化設定單例
settings = Settings()

# 自動建立需要的資料夾
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.AUDIO_DIR, exist_ok=True)