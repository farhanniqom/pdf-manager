# =========================
# Stage 0: Linting
# =========================
FROM python:3.11-slim AS lint
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir flake8

COPY . .

RUN flake8 app/ --exclude=__pycache__,venv --max-line-length=120


# =========================
# Stage 1: Frontend Build
# =========================
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npx tailwindcss -i ./input.css -o ./static/css/output.css


# =========================
# Stage 2: Python Builder
# =========================
FROM python:3.11-slim AS python-builder
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libqpdf-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# =========================
# Stage 3: Final Runtime
# =========================
FROM python:3.11-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libqpdf29 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=python-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY . .

COPY --from=frontend-builder /app/frontend/static/css/output.css ./frontend/static/css/output.css

RUN mkdir -p storage/uploads storage/outputs && \
    chmod -R 755 storage

EXPOSE 9000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]