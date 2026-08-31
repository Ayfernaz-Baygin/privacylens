# Build context is the repository root (see compose.yaml), so that
# `backend/` lands under /app/backend and `uvicorn backend.app.main:app`
# resolves exactly the same import path used in local development.
FROM python:3.13-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt

# PyMuPDF invokes the Tesseract executable directly for scanned PDF
# pages. Keep the engine and the two configured language data sets in
# the runtime image; no Python OCR wrapper is needed.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-tur \
    && rm -rf /var/lib/apt/lists/*

# PrivacyLens runs Turkish NER on CPU only (turkish_ner.py pins
# device=-1, no GPU code path exists), but PyPI's default `torch`
# wheel bundles the full CUDA/NVIDIA runtime (~3.4GB of unused
# nvidia-*/triton packages). Installing the official CPU-only build
# FIRST, from PyTorch's own CPU wheel index, avoids that entirely --
# verified this exact wheel exists for the pinned version/Python/
# platform (torch-2.13.0+cpu-cp313-cp313-manylinux_2_28_x86_64.whl).
#
# requirements.txt is untouched and still lists plain `torch==2.13.0`
# (needed for identical local-dev/CI installs): pip's version matching
# treats an already-installed `2.13.0+cpu` as satisfying that plain
# `==2.13.0` requirement (verified -- "Requirement already satisfied"),
# so the second install step below does not reinstall the GPU build
# over this one.
RUN pip install --no-cache-dir torch==2.13.0+cpu \
    --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/

# Container-appropriate default; still fully overridable via the same
# PRIVACYLENS_UPLOAD_ROOT env var config.py already reads -- nothing in
# the app changes for Docker.
ENV PRIVACYLENS_UPLOAD_ROOT=/app/tmp/privacylens

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
