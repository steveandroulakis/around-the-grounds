# Multi-architecture Dockerfile for Around the Grounds Temporal Worker
FROM python:3.9.23-bookworm

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code (needed for package build)
COPY . .

# Install Python dependencies
RUN uv sync --frozen --no-dev

# Create a non-root user for security
RUN useradd -m -u 1000 worker && \
    chown -R worker:worker /app

# Configure git defaults (as root)
RUN git config --global user.name "steveandroulakis" && \
    git config --global user.email "steve.androulakis@gmail.com"

# Switch to worker user
USER worker

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import asyncio; import around_the_grounds.temporal.config; asyncio.run(around_the_grounds.temporal.config.validate_configuration())"

# Default command
CMD ["uv", "run", "python", "-m", "around_the_grounds.temporal.worker"]