FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc g++ libpq-dev curl git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.render.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.render.txt

# Copy application code
COPY . .

# Create required directories
RUN mkdir -p data/models data/creator_lessons

ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}
