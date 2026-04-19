FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 先裝依賴 — 讓 requirements 層的 cache 獨立於 source code
COPY requirements.txt ./
RUN pip install -r requirements.txt

# 再複製程式
COPY pyproject.toml README.md ./
COPY src ./src
COPY apps ./apps

# 把 repo 當 editable package 裝起來（pyproject 有 setuptools 設定）
RUN pip install --no-deps -e .

EXPOSE 8000

CMD ["uvicorn", "apps.huwei_landmarks.server:app", "--host", "0.0.0.0", "--port", "8000"]
