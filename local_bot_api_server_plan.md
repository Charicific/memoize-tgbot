# Local Telegram Bot API Server Deployment Plan

This document outlines the step-by-step setup to host a self-hosted, local Telegram Bot API Server within your Koyeb cluster. 

By routing outbound requests to a local sidecar service, the bot benefits from **0ms local handshakes** and direct high-performance persistent connection pipelines to Telegram's core data centers.

---

## 1. How it Works (Architecture)

Normally, the bot sends HTTP requests across the public internet to Telegram's servers. By running a local API server:
* Your bot sends messages to a local service on Koyeb's private network (`http://localhost:8081`).
* The local server maintains persistent, optimized connections to Telegram's core servers, processing your requests instantly.

```
[ Bot Container ] --(Local HTTP / <1ms)--> [ Bot API Server (Local Container) ] --(Persistent Sockets)--> [ Telegram Core DC ]
```

---

## 2. Step 1: Obtain Telegram API Credentials

The self-hosted server requires standard Telegram API credentials to register itself with the network:
1. Log in to [my.telegram.org](https://my.telegram.org) with your phone number.
2. Navigate to **API development tools**.
3. Create a profile (fill out the App title and short name).
4. Save your **`App api_id`** and **`App api_hash`**.

---

## 3. Step 2: Deploy the Local API Server on Koyeb

You will deploy a second service inside your Koyeb application space:

1. **Docker Image**: Use the official, highly optimized Bot API image:
   `aiogram/telegram-bot-api:latest`
2. **Ports**: Expose port `8081` internally (do NOT expose it to the public internet).
3. **Environment Variables / Command Arguments**:
   Configure the entrypoint / start command of the container to run:
   ```bash
   telegram-bot-api --api-id=<YOUR_API_ID> --api-hash=<YOUR_API_HASH> --local
   ```
   *(Note: The `--local` flag enables the server to handle local file paths and increases limits).*

---

## 4. Step 3: Configure the Bot Code

Modify the Bot startup in your Python codebase to redirect requests from `api.telegram.org` to the local Koyeb service.

In your main entrypoint file [src/main.py](file:///d:/Projects/memoize-tgbot/src/main.py):

### 1. Import dependencies:
```python
from aiogram.client.telegram import TelegramAPIServer
from aiogram.client.session.aiohttp import AiohttpSession
```

### 2. Configure the server URL:
Define a setting in `src/config.py` for the local server URL, or define it in your environment:
```env
# Add to .env
TELEGRAM_API_SERVER_URL=http://telegram-bot-api-service.koyeb:8081
```

### 3. Modify Bot Initialization:
Update the `bot` object creation in [src/main.py](file:///d:/Projects/memoize-tgbot/src/main.py) (around lines 1215-1225):

```python
    # Set up session with custom API server URL if configured
    session = None
    if settings.TELEGRAM_API_SERVER_URL:
        logger.info(f"Using local Telegram Bot API server at {settings.TELEGRAM_API_SERVER_URL}")
        local_server = TelegramAPIServer.from_base(settings.TELEGRAM_API_SERVER_URL)
        session = AiohttpSession(api=local_server)

    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session
    )
```

---

## 5. Major Benefits

1. **Zero HTTP Handshake Latency**: Message delivery RTT drops to near-instant levels because connections are routed locally on the Koyeb server rack.
2. **Massive File Limits**: The bot can download and upload files up to **2000 MB** (instead of the standard 50 MB / 20 MB limits).
3. **Reduced Memory Overhead**: The local server handles media downloading/uploading internally, freeing up your Python bot process from streaming large file payloads.
