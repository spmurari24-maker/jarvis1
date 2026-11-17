FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JARVIS_HOST=0.0.0.0 \
    JARVIS_AUDIT_PATH=/tmp/jarvis-audit/events.jsonl

WORKDIR /app
COPY pyproject.toml README.md ./
COPY jarvis ./jarvis
COPY config ./config
# The registry loads manifest files from the configured project-root folder.
COPY jarvis/skills ./skills
RUN pip install --no-cache-dir ".[firebase-auth]"

CMD ["sh", "-c", "uvicorn jarvis.api:app --host 0.0.0.0 --port ${PORT:-8080}"]
