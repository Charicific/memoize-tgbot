import io
import logging
from typing import Optional
from aiogram import html, types

logger = logging.getLogger(__name__)


async def send_log(
    text: str,
    pin: bool = False,
    disable_notification: bool = True,
    attachment_text: Optional[str] = None,
    attachment_filename: str = "details.txt",
):
    """
    Sends a formatted HTML log message to the configured private log channel.
    If `attachment_text` is provided, it is sent as a .txt document reply
    so that long tracebacks are not truncated by Telegram's 4096-char limit.
    """
    from src.config import settings

    if not settings.LOG_CHANNEL_ID:
        logger.warning("LOG_CHANNEL_ID is not configured in settings. Log message ignored.")
        return

    # To avoid circular dependency during startup
    from src.main import bot

    try:
        if attachment_text:
            file_bytes = attachment_text.encode("utf-8")
            # Truncate caption if it exceeds Telegram's 1024-character limit
            caption = text
            if len(caption) > 1024:
                caption = caption[:1021] + "..."

            msg = await bot.send_document(
                chat_id=settings.LOG_CHANNEL_ID,
                document=types.BufferedInputFile(file_bytes, filename=attachment_filename),
                caption=caption,
                parse_mode="HTML",
                disable_notification=disable_notification,
            )
        else:
            msg = await bot.send_message(
                chat_id=settings.LOG_CHANNEL_ID,
                text=text,
                parse_mode="HTML",
                disable_notification=disable_notification,
                disable_web_page_preview=True,
            )

        if pin:
            await bot.pin_chat_message(
                chat_id=settings.LOG_CHANNEL_ID,
                message_id=msg.message_id,
                disable_notification=disable_notification,
            )
    except Exception as e:
        logger.error(
            f"Failed to send log to Telegram channel {settings.LOG_CHANNEL_ID}: {e}",
            exc_info=True,
        )


async def send_error_log(
    exception: Exception,
    context_label: str = "Unhandled Exception",
    update=None,
):
    """
    Convenience helper for structured error logging.
    Sends a short one-liner to the log channel with the full traceback
    and optional update JSON attached as a .txt file.
    """
    import traceback
    from html import escape as html_escape

    tb = "".join(
        traceback.format_exception(type(exception), exception, exception.__traceback__)
    )

    short_msg = (
        f"🚨 {html.bold(f'CRITICAL: {context_label}')} 🚨\n\n"
        f"⚠️ {html.bold('Error:')} {html.code(str(exception))}"
    )

    # Build full attachment text
    attachment_lines = [
        f"=== {context_label} ===",
        "",
        "FULL TRACEBACK:",
        tb,
    ]
    if update is not None:
        try:
            update_json = update.model_dump_json(indent=2)
        except Exception:
            update_json = str(update)
        attachment_lines += ["", "TRIGGERING UPDATE (JSON):", update_json]

    attachment_text = "\n".join(attachment_lines)

    await send_log(
        text=short_msg,
        pin=True,
        disable_notification=False,
        attachment_text=attachment_text,
        attachment_filename="error_details.txt",
    )


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
