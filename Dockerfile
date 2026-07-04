# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Versos backend — FastAPI + NeMo Agent Toolkit (slim deploy image).
# Runs all three verticals. To add Guardrails/Presidio/Phoenix later, uncomment
# the EXTRAS block below (no code change needed elsewhere).
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build deps for any packages without wheels; removed after install to stay slim.
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

# 1) Python deps first (cached layer). Slim set only.
COPY requirements-deploy.txt requirements-extras.txt ./
RUN pip install --upgrade pip && pip install -r requirements-deploy.txt

# --- EXTRAS (Guardrails / Presidio / Phoenix). Uncomment to enable later: ---
# RUN pip install -r requirements-extras.txt \
#  && pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

# 2) App source + the NAT workflow package (editable install triggers registration).
COPY backend/ ./backend/
COPY nat_sandbox/ ./nat_sandbox/
RUN pip install -e nat_sandbox/severity_lab

# Non-root runtime.
RUN useradd --create-home appuser
USER appuser

# DATABASE_URL, NVIDIA_API_KEY, CORS_ORIGINS are injected at runtime (never baked in).
EXPOSE 8090
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8090"]
