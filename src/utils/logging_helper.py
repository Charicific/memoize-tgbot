import logging
from typing import Optional
from aiogram import html, types

logger = logging.getLogger(__name__)

async def send_log(text: str, pin: bool = False, disable_notification: bool = True):
    """
    Sends a formatted HTML log message to the configured private log channel.
    Optionally pins the message and configures message notification severity.
    """
    from src.config import settings
    
    if not settings.LOG_CHANNEL_ID:
        logger.warning("LOG_CHANNEL_ID is not configured in settings. Log message ignored.")
        return

    # To avoid circular dependency during startup
    from src.main import bot

    try:
        msg = await bot.send_message(
            chat_id=settings.LOG_CHANNEL_ID,
            text=text,
            parse_mode="HTML",
            disable_notification=disable_notification,
            disable_web_page_preview=True
        )
        if pin:
            await bot.pin_chat_message(
                chat_id=settings.LOG_CHANNEL_ID,
                message_id=msg.message_id,
                disable_notification=disable_notification
            )
    except Exception as e:
        logger.error(f"Failed to send log to Telegram channel {settings.LOG_CHANNEL_ID}: {e}", exc_info=True)


async def log_admin_activity(action_text: str, message: types.Message):
    """
    Logs administrative actions, appending the source message link if available.
    """
    log_msg = action_text
    
    try:
        url = message.get_url()
        if url:
            log_msg += f"\n• {html.bold('Source Message:')} <a href='{url}'>Link</a>"
    except Exception:
        pass
        
    await send_log(log_msg, disable_notification=False)

