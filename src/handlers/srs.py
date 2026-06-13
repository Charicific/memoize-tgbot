import logging
from aiogram import Router, F, html
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from src.services.supabase_db import db
from src.services.leetcode import LeetCodeClient
from src.services.redis_cache import cache_manager
from src.services.srs_service import srs_service

router = Router()
logger = logging.getLogger(__name__)

leetcode_client = LeetCodeClient()

@router.message(Command("solved"))
async def cmd_solved(message: Message, command: CommandObject):
    user_id = message.from_user.id
    
    if await cache_manager.is_rate_limited(user_id, "solved", limit=5, period=10):
        await message.reply("Too many requests. Please wait a bit.")
        return

    # Check if LeetCode is linked
    link = await db.get_linked_account(user_id)
    if not link or not link["verified"]:
        await message.reply(f"⚠️ You must link and verify your LeetCode account first using {html.code('/link &lt;username&gt;')}!", parse_mode="HTML")
        return

    leetcode_username = link["leetcode_username"]

    # Optional manual logging: /solved <problem_slug> <quality>
    if command.args:
        parts = command.args.split()
        if len(parts) == 2:
            problem_slug = parts[0].strip()
            try:
                quality = int(parts[1])
                if not (0 <= quality <= 5):
                    raise ValueError()
            except ValueError:
                await message.reply("⚠️ Quality must be an integer between 0 and 5.")
                return

            await message.reply("⏳ Logging your solved problem... Please wait.")
            # Fetch problem details to get title and difficulty
            problem = await leetcode_client.get_problem_details(problem_slug)
            if not problem:
                await message.reply(f"❌ Could not find LeetCode problem with slug {html.code(problem_slug)}.", parse_mode="HTML")
                return

            # Record in problem history and SRS
            await db.record_solved_problem(user_id, problem_slug, problem["title"], problem["difficulty"])
            await srs_service.log_review(user_id, problem_slug, quality)
            await db.add_xp_coins(user_id, xp=15, coins=5)

            await message.reply(
                f"✅ Successfully logged review for {html.bold(problem['title'])}!\n"
                f"🧠 SM-2 quality: {quality}/5\n"
                f"🎁 Awarded 15 XP and 5 coins.",
                parse_mode="HTML"
            )
            return

    # Interactive flow
    await message.reply("🔍 Fetching your recent LeetCode accepted submissions...")

    submissions = await leetcode_client.get_recent_accepted_submissions(leetcode_username, limit=5)
    if not submissions:
        await message.reply("❌ No recent accepted submissions found on your LeetCode profile. Make sure you solved a problem recently!")
        return

    # Cache submissions list in Redis for 10 minutes
    cache_key = f"recent_subs:{user_id}"
    await cache_manager.set(cache_key, submissions, expire_seconds=600)

    # Build keyboard
    keyboard_buttons = []
    for idx, sub in enumerate(submissions):
        button_text = f"🏆 {sub['title']}"
        keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"srs_select:{idx}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.reply("🎯 Which problem did you just solve and want to log for spaced repetition?", reply_markup=keyboard)


@router.callback_query(F.data.startswith("srs_select:"))
async def process_srs_select(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    idx = int(callback_query.data.split(":")[1])

    # Fetch cached submissions
    cache_key = f"recent_subs:{user_id}"
    submissions = await cache_manager.get(cache_key)
    
    if not submissions or idx >= len(submissions):
        await callback_query.answer("⚠️ Session expired. Please run /solved again.", show_alert=True)
        return

    selected_sub = submissions[idx]
    problem_slug = selected_sub["titleSlug"]
    problem_title = selected_sub["title"]

    # Keyboard for rating
    # Options 0 to 5
    ratings = [
        ("🔴 0 - Forgot", "0"),
        ("🟠 1 - Hard", "1"),
        ("🟡 2 - Slow", "2"),
        ("🔵 3 - Medium", "3"),
        ("🟢 4 - Easy", "4"),
        ("⭐ 5 - Perfect", "5")
    ]
    
    keyboard_buttons = []
    # Make buttons in 2 columns
    row = []
    for text, val in ratings:
        row.append(InlineKeyboardButton(text=text, callback_data=f"srs_rate:{idx}:{val}"))
        if len(row) == 2:
            keyboard_buttons.append(row)
            row = []
            
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback_query.message.edit_text(
        text=f"🧠 How would you rate your recall/mastery for {html.bold(problem_title)}?\n\n"
             "• 5: Perfect recall, solved instantly\n"
             "• 4: Solved easily after slight thinking\n"
             "• 3: Solved with moderate effort / time\n"
             "• 2: Solved but struggled or took too long\n"
             "• 1: Struggled heavily, code has major flaws\n"
             "• 0: Completely forgot the approach / had to look at solution",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith("srs_rate:"))
async def process_srs_rate(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    parts = callback_query.data.split(":")
    idx = int(parts[1])
    quality = int(parts[2])

    # Fetch cached submissions
    cache_key = f"recent_subs:{user_id}"
    submissions = await cache_manager.get(cache_key)
    
    if not submissions or idx >= len(submissions):
        await callback_query.answer("⚠️ Session expired. Please run /solved again.", show_alert=True)
        return

    selected_sub = submissions[idx]
    problem_slug = selected_sub["titleSlug"]
    problem_title = selected_sub["title"]

    await callback_query.message.edit_text("⏳ Processing review scheduling...")

    # Fetch full problem details to get difficulty
    problem = await leetcode_client.get_problem_details(problem_slug)
    difficulty = problem["difficulty"] if problem else "Medium"

    # Record solved problem & srs review
    await db.record_solved_problem(user_id, problem_slug, problem_title, difficulty)
    record = await srs_service.log_review(user_id, problem_slug, quality)
    await db.add_xp_coins(user_id, xp=15, coins=5)

    next_date = record["next_review_date"]
    if isinstance(next_date, str):
        # Parse datetime if string
        try:
            next_date = datetime.datetime.fromisoformat(next_date.replace("Z", "+00:00"))
        except ValueError:
            pass

    next_date_str = next_date.strftime("%d %b %Y, %I:%M %p") if hasattr(next_date, "strftime") else str(next_date)

    success_msg = (
        f"✅ {html.bold('Review Logged successfully!')}\n\n"
        f"🏆 Problem: {html.bold(problem_title)}\n"
        f"📊 Recall Quality: {quality}/5\n"
        f"📅 Next Review Due: {html.code(next_date_str)}\n"
        f"🔁 Interval Scheduled: {html.bold(record['interval'])} day(s)\n"
        f"📈 Ease Factor: {record['ease_factor']:.2f}\n\n"
        f"🎁 Awarded {html.bold('15 XP')} and {html.bold('5 coins')}!"
    )
    
    await callback_query.message.edit_text(success_msg, parse_mode="HTML")
    await callback_query.answer("Review Logged!")
