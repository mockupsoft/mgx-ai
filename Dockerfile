# Multi-stage build for MGX Agent API

# ============================================
# Stage 1: Builder
# ============================================
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Create a virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --use-deprecated=legacy-resolver -r requirements.txt

# ============================================
# Stage 2: Runtime
# ============================================
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY . .

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Patch MetaGPT GeminiLLM to use config model instead of hardcoded "gemini-pro"
RUN sed -i 's/self\.model = "gemini-pro"/self.model = self.config.model or "gemini-2.0-flash"/g' \
    /opt/venv/lib/python3.11/site-packages/metagpt/provider/google_gemini_api.py && \
    sed -i 's/self\.llm = GeminiGenerativeModel(model_name=self\.model)/self.llm = GeminiGenerativeModel(model_name=self.config.model or self.model)/g' \
    /opt/venv/lib/python3.11/site-packages/metagpt/provider/google_gemini_api.py

# Create non-root user with proper HOME
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
ENV HOME=/home/appuser
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health/', timeout=5)"

# Expose port
EXPOSE 8000

# Use entrypoint to create config before starting
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
