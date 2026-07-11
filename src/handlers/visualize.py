import logging
import base64
import json
import zlib
import httpx
from aiogram import Router, html
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, BufferedInputFile
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

    try:
        # Call AI service
        result = await ai_service.generate_flowchart_mermaid(code)
        if not result:
            await progress_msg.edit_text("❌ Failed to generate flowchart visualization. Please try again later.")
            return

        mermaid_code, trace_steps = result
    except Exception as e:
        logger.error(f"Error in cmd_visualize: {e}", exc_info=True)
        await progress_msg.edit_text(f"❌ {e}")
        return
    logger.info(f"Generated Mermaid syntax:\n{mermaid_code}")

    from src.utils.formatters import clean_leetcode_html
    trace_steps = clean_leetcode_html(trace_steps)

    try:
        # 1. Prepare JSON structure & compress using zlib (pako format)
        j_graph = {"code": mermaid_code, "mermaid": {"theme": "default"}}
        byte_str = json.dumps(j_graph).encode('utf-8')
        compress = zlib.compressobj(9, zlib.DEFLATED, 15, 8, zlib.Z_DEFAULT_STRATEGY)
        deflated = compress.compress(byte_str) + compress.flush()
        
        # 2. Base64 encode and make URL-safe
        b64 = base64.b64encode(deflated).decode('ascii')
        safe_b64 = b64.replace('+', '-').replace('/', '_')
        photo_url = f"https://mermaid.ink/img/pako:{safe_b64}"
        
        # 3. Download the rendering directly from mermaid.ink to upload it as bytes
        logger.info(f"Downloading flowchart image from: {photo_url}")
        async with httpx.AsyncClient(http2=True, timeout=15.0) as client:
            img_response = await client.get(photo_url)
            img_response.raise_for_status()
            photo_bytes = img_response.content
            
        photo_file = BufferedInputFile(photo_bytes, filename="flowchart.png")
        
        caption_text = (
            f"📊 {html.bold('Execution Flowchart & Trace')}\n\n"
            f"{trace_steps}"
        )

        # Check caption limit (Telegram has a 1024-character caption limit for photos)
        if len(caption_text) <= 1024:
            await message.bot.send_photo(
                chat_id=message.chat.id,
                photo=photo_file,
                caption=caption_text,
                parse_mode="HTML",
                reply_to_message_id=message.message_id
            )
            await progress_msg.delete()
        else:
            # Send photo and follow up with the full trace details in a text message
            await message.bot.send_photo(
                chat_id=message.chat.id,
                photo=photo_file,
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
