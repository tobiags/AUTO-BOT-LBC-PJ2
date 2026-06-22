FROM python:3.12-slim

WORKDIR /app

# System deps: asyncpg (libpq), patchright/Playwright browser stack
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    wget \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2t64 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgtk-3-0 \
    libx11-6 \
    libxcb1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Copy source (hatchling needs the full package tree to build)
COPY . .

# Install Python packages
RUN pip install --no-cache-dir .

# Install patchright browser (Chromium + stealth patches)
RUN patchright install chromium --with-deps || true

# Default: FastAPI API (Celery worker overrides CMD via Coolify start_command)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
