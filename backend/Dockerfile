FROM python:3.11-slim-bookworm

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    poppler-utils \
    build-essential \
    make \
    gcc \
    g++ \
    swig \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install PyMuPDF in its own layer (compiles from source ~7min first time, cached after)
# PaddleOCR 2.7.0.3 requires PyMuPDF<1.21.0 which has no pre-built wheels
RUN pip install --no-cache-dir "PyMuPDF<1.21.0"

# Install heavy ML packages (PyMuPDF already satisfied from above)
RUN pip install --no-cache-dir \
    paddlepaddle==2.6.2 \
    paddleocr==2.7.0.3

# Install other ML packages
RUN pip install --no-cache-dir \
    sentence-transformers==2.3.1 \
    numpy==1.26.4

# Install remaining requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/uploads /app/chroma_data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
