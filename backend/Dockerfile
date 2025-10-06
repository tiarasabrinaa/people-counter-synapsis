# Backend Dockerfile
FROM python:3.9-slim-bookworm

# Set working directory
WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency file
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files from backend/
COPY . .

# Pastikan Python tahu path-nya
ENV PYTHONPATH=/app

# Expose API port
EXPOSE 8000

# Healthcheck (optional tapi recommended)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Jalankan aplikasi utama
CMD ["python", "-m", "app.main"]
