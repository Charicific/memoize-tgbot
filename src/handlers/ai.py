import logging
from aiogram import Router, F, html
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from src.services.leetcode import LeetCodeClient
from src.services.ai_service import ai_service
from src.services.redis_cache import cache_manager

router = Router()
logger = logging.getLogger(__name__)

leetcode_client = LeetCodeClient()

@router.message(Command("hint"))
async def cmd_hint(message: Message, command: CommandObject):
    user_id = message.from_user.id
    if await cache_manager.is_rate_limited(user_id, "hint", limit=5, period=60):
        await message.reply("⚠️ AI limits exceeded. Please wait 1 minute before asking for another hint.")
        return

    if not command.args:
        await message.reply("⚠️ Please specify the problem slug:\nExample: `/hint two-sum`", parse_mode="HTML")
        return

    problem_slug = command.args.strip()
    await message.reply(f"🤖 Fetching problem '{problem_slug}' and compiling AI hints...")

    # Fetch problem details from LeetCode
    problem = await leetcode_client.get_problem_details(problem_slug)
    if not problem:
        await message.reply("❌ Could not find the problem on LeetCode. Please double-check the slug.")
        return

    # Extract info
    title = problem["title"]
    description = problem["content"]
    code_templates = "\n".join([f"{item['lang']}:\n{item['code']}" for item in problem.get("codeSnippets", [])])

    # Call AI service
    hints = await ai_service.generate_progressive_hints(title, description, code_templates)
    if not hints:
        await message.reply("❌ Error generating hints. Please try again later.")
        return

    # Cache hints: a tuple (hint1, hint2, hint3)
    cache_key = f"hints:{user_id}:{problem_slug}"
    await cache_manager.set(cache_key, list(hints), expire_seconds=1800) # Cache for 30 minutes

    # Show Hint 1
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💡 Get Hint 2", callback_data=f"ai_hint:{problem_slug}:2")]
    ])

    await message.reply(
        f"🤖 {html.bold('Progressive Hints for ' + title)}\n\n"
        f"💡 {html.bold('Hint 1 (Conceptual):')}\n"
        f"{hints[0]}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


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
            f"{callback_query.message.text}\n\n"
            f"💡 {html.bold('Hint 2 (Strategic):')}\n"
            f"{hints[1]}"
        )
        await callback_query.message.edit_text(new_text, reply_markup=keyboard, parse_mode="HTML")
    
    elif requested_hint_level == 3:
        # Final hint level
        new_text = (
            f"{callback_query.message.text}\n\n"
            f"💡 {html.bold('Hint 3 (Detailed Pseudo-code):')}\n"
            f"{hints[2]}"
        )
        await callback_query.message.edit_text(new_text, parse_mode="HTML")

    await callback_query.answer()


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

    analysis = await ai_service.analyze_complexity(code)
    if not analysis:
        await message.reply("❌ Could not analyze the code. Please try again.")
        return

    await message.reply(analysis, parse_mode="HTML")


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

    await message.reply("🤖 Performing detailed code review using Gemini Flash 2.0... Please wait.")

    # We can try to extract a problem title if they paste context, or just pass generic title
    review = await ai_service.generate_code_review(
        problem_title="User Submitted Code",
        problem_description="N/A (General code review)",
        user_code=code
    )

    if not review:
        await message.reply("❌ Code review failed. Please try again.")
        return

    # Check length
    if len(review) > 4096:
        for i in range(0, len(review), 4000):
            await message.reply(review[i:i+4000], parse_mode="HTML")
    else:
        await message.reply(review, parse_mode="HTML")
