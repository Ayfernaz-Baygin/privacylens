# Build context is the repository root (see compose.yaml), so that
# `backend/` lands under /app/backend and `uvicorn backend.app.main:app`
# resolves exactly the same import path used in local development.
FROM python:3.13-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/

# Container-appropriate default; still fully overridable via the same
# PRIVACYLENS_UPLOAD_ROOT env var config.py already reads -- nothing in
# the app changes for Docker.
ENV PRIVACYLENS_UPLOAD_ROOT=/app/tmp/privacylens

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
