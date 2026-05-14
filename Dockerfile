# HR Compliance Analytics — Docker
# Multi-stage build: slim runtime with pre-installed dependencies

FROM python:3.11-slim-bookworm AS builder

RUN pip install --no-cache-dir --upgrade pip

# Install only what's needed at runtime
FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="HR Compliance Analytics"
LABEL org.opencontainers.image.description="Plataforma de auditoria trabalhista inteligente — labor audit & people analytics"
LABEL org.opencontainers.image.authors="HR Compliance Analytics Team"

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r hrc && useradd -r -g hrc -m -d /home/hrc hrc

WORKDIR /app

# Install Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=hrc:hrc . .

# Create data directories with proper permissions
RUN mkdir -p data/bronze data/silver data/gold data/gold/governance \
    && chown -R hrc:hrc /app

USER hrc

EXPOSE 8050

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fs http://localhost:8050/ || exit 1

# Entrypoint: generate data if needed, then launch dashboards
COPY docker-entrypoint.sh /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["app"]
