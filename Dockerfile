FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴（Azure Speech 需要）
RUN apt-get update && apt-get install -y \
    gcc \
    ffmpeg \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 使用 uv 安裝依賴（超快）
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv pip install --system --no-cache -r <(uv pip compile pyproject.toml)

# 複製程式碼
COPY backend ./backend
COPY knowledge_base ./knowledge_base

# 暴露端口
EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]