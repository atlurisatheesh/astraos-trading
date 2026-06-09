FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc g++ libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (uses render-optimised requirements)
COPY requirements.render.txt .
RUN pip install --no-cache-dir -r requirements.render.txt

# Copy application code
COPY . .

# Create required directories
RUN mkdir -p data/models data/creator_lessons

# Non-root user for security
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}
