import logging
import base64
from aiogram import Router, html
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from src.services.ai_service import ai_service
from src.services.redis_cache import cache_manager

router = Router()
logger = logging.getLogger(__name__)

@router.message(Command("visualize"))
async def cmd_visualize(message: Message, command: CommandObject):
    user_id = message.from_user.id
    if await cache_manager.is_rate_limited(user_id, "visualize", limit=3, period=60):
        await message.reply("⚠️ AI limits exceeded. Please wait 1 minute before requesting another visualization.")
        return

    # Retrieve code snippet
    code = ""
    if command.args:
        code = command.args.strip()
    elif message.reply_to_message and message.reply_to_message.text:
        code = message.reply_to_message.text.strip()

    if not code:
        await message.reply(
            "⚠️ Please provide a code snippet to visualize!\n"
            "Example: `/visualize def solve(): ...` or reply `/visualize` to a message containing code.",
            parse_mode="HTML"
        )
        return

    progress_msg = await message.reply("🤖 Analyzing code execution path and generating flowchart... Please wait.")

    # Call AI service
    result = await ai_service.generate_flowchart_mermaid(code)
    if not result:
        await progress_msg.edit_text("❌ Failed to generate flowchart visualization. Please try again later.")
        return

    mermaid_code, trace_steps = result
    logger.info(f"Generated Mermaid syntax:\n{mermaid_code}")

    from src.utils.formatters import clean_leetcode_html
    trace_steps = clean_leetcode_html(trace_steps)

    try:
        # Base64 encode the mermaid code for the mermaid.ink URL
        # Standard base64 is supported by mermaid.ink
        encoded_bytes = base64.b64encode(mermaid_code.encode("utf-8"))
        encoded_str = encoded_bytes.decode("utf-8")
        
        # Build image URL
        photo_url = f"https://mermaid.ink/img/{encoded_str}"
        
        caption_text = (
            f"📊 {html.bold('Execution Flowchart & Trace')}\n\n"
            f"{trace_steps}"
        )

        # Check caption limit (Telegram has a 1024-character caption limit for photos)
        if len(caption_text) <= 1024:
            await message.bot.send_photo(
                chat_id=message.chat.id,
                photo=photo_url,
                caption=caption_text,
                parse_mode="HTML",
                reply_to_message_id=message.message_id
            )
            await progress_msg.delete()
        else:
            # Send photo and follow up with the full trace details in a text message
            await message.bot.send_photo(
                chat_id=message.chat.id,
                photo=photo_url,
                caption=f"📊 {html.bold('Execution Flowchart')}",
                parse_mode="HTML",
                reply_to_message_id=message.message_id
            )
            await progress_msg.delete()
            # Send trace text
            await message.reply(trace_steps, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error rendering flowchart: {e}", exc_info=True)
        from html import escape as html_escape
        # Fallback to sending the raw Mermaid block
        fallback_msg = (
            f"❌ Renders failed, sending raw Mermaid flowchart:\n\n"
            f"<pre><code class='language-mermaid'>{html_escape(mermaid_code)}</code></pre>\n\n"
            f"{trace_steps}"
        )
        await progress_msg.edit_text(fallback_msg, parse_mode="HTML")
