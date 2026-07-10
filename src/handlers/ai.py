import logging
from aiogram import Router, F, html
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from src.services.leetcode import LeetCodeClient
from src.services.ai_service import ai_service
from src.services.redis_cache import cache_manager
from src.utils.formatters import format_markdown_to_html

router = Router()
logger = logging.getLogger(__name__)

leetcode_client = LeetCodeClient()

async def generate_and_send_hints(message: Message, user_id: int, problem: dict):
    problem_slug = problem["titleSlug"]
    title = problem["title"]
    description = problem["content"]
    code_templates = "\n".join([f"{item['lang']}:\n{item['code']}" for item in problem.get("codeSnippets", [])])

    try:
        hints = await ai_service.generate_progressive_hints(title, description, code_templates)
        if not hints:
            await message.reply("❌ Error generating hints. Please try again later.")
            return
    except Exception as e:
        logger.error(f"Error in generate_and_send_hints: {e}", exc_info=True)
        await message.reply(f"❌ {e}")
        return

    # Cache hints
    cache_key = f"hints:{user_id}:{problem_slug}"
    await cache_manager.set(cache_key, list(hints), expire_seconds=1800)

    # Show Hint 1
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💡 Get Hint 2", callback_data=f"ai_hint:{problem_slug}:2")]
    ])

    num_prefix = ""
    if problem.get("questionFrontendId"):
        num_prefix = f"{problem['questionFrontendId']}. "

    await message.reply(
        f"🤖 {html.bold('Progressive Hints for ' + num_prefix + title)}\n\n"
        f"💡 {html.bold('Hint 1 (Conceptual):')}\n"
        f"{format_markdown_to_html(hints[0])}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.message(Command("hint"))
async def cmd_hint(message: Message, command: CommandObject):
    user_id = message.from_user.id
    if await cache_manager.is_rate_limited(user_id, "hint", limit=5, period=60):
        await message.reply("⚠️ AI limits exceeded. Please wait 1 minute before asking for another hint.")
        return

    if not command.args:
        await message.reply("⚠️ Please specify the LeetCode problem (number or title):\nExample: `/hint 1` or `/hint two sum`", parse_mode="HTML")
        return

    problem_query = command.args.strip()
    status_msg = await message.reply(f"🤖 Searching LeetCode for '{problem_query}'...")

    # Resolve using fuzzy/number search resolver
    matches = await leetcode_client.resolve_problem_query(problem_query)
    if not matches:
        await status_msg.edit_text(f"❌ Could not find any problems matching '{problem_query}'.")
        return

    if len(matches) == 1:
        # Exact match
        problem_slug = matches[0]["titleSlug"]
        # Fetch detailed problem details to generate hints
        problem = await leetcode_client.get_problem_details(problem_slug)
        if not problem:
            await status_msg.edit_text("❌ Could not retrieve problem details from LeetCode.")
            return
        await status_msg.delete()
        await generate_and_send_hints(message, user_id, problem)
        return

    # Multiple matches - show selection menu
    await status_msg.delete()
    keyboard_buttons = []
    for q in matches[:5]:
        button_text = f"💡 {q['frontendQuestionId']}. {q['title']}"
        keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"hint_select:{q['titleSlug']}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.reply(f"🔍 Multiple matching problems found for '{problem_query}'. Please select one:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("hint_select:"))
async def process_hint_select(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    problem_slug = callback_query.data.split(":")[1]

    if await cache_manager.is_rate_limited(user_id, "hint", limit=5, period=60):
        await callback_query.answer("⚠️ AI limits exceeded. Please wait 1 minute.", show_alert=True)
        return

    # Fetch detailed problem details
    problem = await leetcode_client.get_problem_details(problem_slug)
    if not problem:
        await callback_query.answer("❌ Could not retrieve problem details.", show_alert=True)
        return

    await callback_query.message.delete()
    await generate_and_send_hints(callback_query.message, user_id, problem)
    await callback_query.answer()


@router.callback_query(F.data.startswith("ai_hint:"))
async def process_ai_hint(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    parts = callback_query.data.split(":")
    problem_slug = parts[1]
    requested_hint_level = int(parts[2])

    # Fetch cached hints
    cache_key = f"hints:{user_id}:{problem_slug}"
    hints = await cache_manager.get(cache_key)

    if not hints or len(hints) < 3:
        await callback_query.answer("⚠️ Session expired. Please run /hint again.", show_alert=True)
        return

    # Render appropriate hint
    if requested_hint_level == 2:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💡 Get Hint 3 (Detailed)", callback_data=f"ai_hint:{problem_slug}:3")]
        ])
        
        # We append Hint 2 to the message
        new_text = (
            f"{callback_query.message.html_text}\n\n"
            f"💡 {html.bold('Hint 2 (Strategic):')}\n"
            f"{format_markdown_to_html(hints[1])}"
        )
        await callback_query.message.edit_text(new_text, reply_markup=keyboard, parse_mode="HTML")
    
    elif requested_hint_level == 3:
        # Final hint level
        new_text = (
            f"{callback_query.message.html_text}\n\n"
            f"💡 {html.bold('Hint 3 (Detailed Pseudo-code):')}\n"
            f"{format_markdown_to_html(hints[2])}"
        )
        await callback_query.message.edit_text(new_text, parse_mode="HTML")

    await callback_query.answer()


def split_markdown(text: str, max_chunk_size: int = 3800) -> list[str]:
    chunks = []
    lines = text.splitlines(keepends=True)
    current_chunk = []
    current_length = 0
    in_code_block = False
    code_block_lang = ""

    for line in lines:
        line_len = len(line)
        # Check if the line changes code block state
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            if in_code_block:
                code_block_lang = line.strip()[3:]  # e.g. "python", "cpp"
            else:
                code_block_lang = ""

        # If adding this line exceeds the chunk size limit
        if current_length + line_len > max_chunk_size:
            # If we are inside a code block, close it before finishing the chunk
            if in_code_block:
                current_chunk.append("```\n")
            
            chunks.append("".join(current_chunk))
            
            # Start next chunk
            current_chunk = []
            if in_code_block:
                # Reopen code block in the next chunk
                current_chunk.append(f"```{code_block_lang}\n")
                current_length = len(current_chunk[-1])
            else:
                current_length = 0

        current_chunk.append(line)
        current_length += line_len

    if current_chunk:
        chunks.append("".join(current_chunk))
    return chunks


@router.message(Command("analyze"))
async def cmd_analyze(message: Message, command: CommandObject):
    user_id = message.from_user.id
    if await cache_manager.is_rate_limited(user_id, "analyze", limit=3, period=60):
        await message.reply("⚠️ AI limits exceeded. Please wait 1 minute before asking for another analysis.")
        return

    # Retrieve code
    code = ""
    if command.args:
        code = command.args.strip()
    elif message.reply_to_message and message.reply_to_message.text:
        code = message.reply_to_message.text.strip()

    if not code:
        await message.reply(
            "⚠️ Please provide a code snippet to analyze!\n"
            "Example: `/analyze def solve(): ...` or reply `/analyze` to a message containing code.",
            parse_mode="HTML"
        )
        return

    await message.reply("🤖 Analyzing time and space complexity... Please wait.")

    try:
        analysis = await ai_service.analyze_complexity(code)
        if not analysis:
            await message.reply("❌ Could not analyze the code. Please try again.")
            return

        chunks = split_markdown(analysis)
        for chunk in chunks:
            await message.reply(format_markdown_to_html(chunk), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in cmd_analyze: {e}", exc_info=True)
        await message.reply(f"❌ {e}")


@router.message(Command("review"))
async def cmd_review(message: Message, command: CommandObject):
    user_id = message.from_user.id
    if await cache_manager.is_rate_limited(user_id, "review", limit=2, period=60):
        await message.reply("⚠️ AI limits exceeded. Please wait 1 minute before requesting another code review.")
        return

    # Retrieve code
    code = ""
    if command.args:
        code = command.args.strip()
    elif message.reply_to_message and message.reply_to_message.text:
        code = message.reply_to_message.text.strip()

    if not code:
        await message.reply(
            "⚠️ Please provide a code snippet to review!\n"
            "Example: `/review def solve(): ...` or reply `/review` to a message containing code.",
            parse_mode="HTML"
        )
        return

    await message.reply("🤖 Performing detailed code review... Please wait.")

    try:
        # We can try to extract a problem title if they paste context, or just pass generic title
        review = await ai_service.generate_code_review(
            problem_title="User Submitted Code",
            problem_description="N/A (General code review)",
            user_code=code
        )

        if not review:
            await message.reply("❌ Code review failed. Please try again.")
            return

        chunks = split_markdown(review)
        for chunk in chunks:
            await message.reply(format_markdown_to_html(chunk), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in cmd_review: {e}", exc_info=True)
        await message.reply(f"❌ {e}")
