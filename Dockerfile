# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Versos backend — FastAPI + NeMo Agent Toolkit. Multi-stage: a builder installs
# everything into a venv; the runtime image copies ONLY the venv + source (no gcc,
# no pip cache, no build tooling) → smaller, faster cold starts.
#
# Ships: slim runtime deps + NeMo Guardrails (flag-gated at runtime).
# Does NOT ship: Presidio/spaCy (PII masking is a dependency-free regex masker) or
# Phoenix/eval (dev-only). See requirements-extras.txt to add those back.
# ---------------------------------------------------------------------------

# ---------- builder ----------
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1
# gcc + g++: NeMo Guardrails pulls `annoy` (C++ ext) with no py3.12 wheel → it compiles from source.
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /app

# Deps first (cached layer): slim set + NeMo Guardrails only.
COPY requirements-deploy.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements-deploy.txt \
    && pip install nemoguardrails==0.22.0

# The NAT workflow package (editable install triggers component registration).
COPY nat_sandbox/ ./nat_sandbox/
RUN pip install -e nat_sandbox/severity_lab

# ---------- runtime ----------
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app

# The prebuilt venv + the source the editable install + config files point at.
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/nat_sandbox /app/nat_sandbox
COPY backend/ ./backend/

RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

# DATABASE_URL, NVIDIA_API_KEY, CORS_ORIGINS are injected at runtime (never baked in).
EXPOSE 8090
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8090"]
