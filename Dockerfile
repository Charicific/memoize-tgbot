# Multi-stage build to copy pre-compiled telegram-bot-api binary from official Alpine image
FROM aiogram/telegram-bot-api:latest AS telegram-api

FROM python:3.11-alpine

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Copy telegram-bot-api binary from the first stage
COPY --from=telegram-api /usr/local/bin/telegram-bot-api /usr/local/bin/telegram-bot-api

# Install runtime dependencies of telegram-bot-api, libpq, and build tools
RUN apk add --no-cache libstdc++ libssl3 zlib libpq curl

# Set working directory
WORKDIR /app

# Copy requirements and compile python dependencies
COPY requirements.txt .
RUN apk add --no-cache --virtual .build-deps build-base postgresql-dev libffi-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps

# Copy source code and entrypoint
COPY src/ ./src/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Expose server port (FastAPI/Webhook port) and local Bot API port
EXPOSE 8000 8081

# Start command via entrypoint script
CMD ["./entrypoint.sh"]
