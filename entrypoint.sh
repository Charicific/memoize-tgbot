#!/bin/sh

# Exit on error
set -e

# Start Telegram API Server in the background if API credentials are provided
if [ -n "$TELEGRAM_API_ID" ] && [ -n "$TELEGRAM_API_HASH" ]; then
    echo "Starting local Telegram Bot API Server..."
    
    # Expose port 8081, run in local mode to support raw file uploads up to 2GB
    telegram-bot-api --api-id="$TELEGRAM_API_ID" --api-hash="$TELEGRAM_API_HASH" --local &
    
    # Wait for the API server to spin up and bind to port 8081
    echo "Waiting for API server to bind to port 8081..."
    sleep 3
else
    echo "TELEGRAM_API_ID and/or TELEGRAM_API_HASH not set. Skipping local Telegram Bot API Server."
fi

# Run the python FastAPI application in the foreground
echo "Starting Memoize Bot..."
exec python -m src.main
