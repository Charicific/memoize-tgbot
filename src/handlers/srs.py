import logging
import datetime
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

async def log_and_send_srs_success(message_or_callback, user_id: int, problem_slug: str, problem_title: str, difficulty: str, quality: int):
    # Record solved problem & srs review
    await db.record_solved_problem(user_id, problem_slug, problem_title, difficulty)
    record = await srs_service.log_review(user_id, problem_slug, quality)
    await db.add_xp_coins(user_id, xp=15, coins=5)

    next_date = record["next_review_date"]
    if isinstance(next_date, str):
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
    
    if isinstance(message_or_callback, Message):
        await message_or_callback.reply(success_msg, parse_mode="HTML")
    elif isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(success_msg, parse_mode="HTML")


async def filter_solved_problems(user_id: int, leetcode_username: str, matches: list) -> list:
    """
    Filters the resolved problem matches to only include ones that the user has actually solved.
    Checks the local database problem history first, then falls back to fetching the user's
    last 20 accepted submissions from LeetCode.
    """
    history = await db.get_problem_history(user_id)
    solved_slugs = {h["problem_slug"] for h in history}

    try:
        recent_subs = await leetcode_client.get_recent_accepted_submissions(leetcode_username, limit=20)
        for sub in recent_subs:
            solved_slugs.add(sub["titleSlug"])
    except Exception as e:
        logger.error(f"Error fetching recent submissions in filter_solved_problems for {leetcode_username}: {e}")

    return [m for m in matches if m["titleSlug"] in solved_slugs]


@router.message(Command("solved"))
async def cmd_solved(message: Message, command: CommandObject):
    user_id = message.from_user.id
    
    if await cache_manager.is_rate_limited(user_id, "solved", limit=5, period=10):
        await message.reply("Too many requests. Please wait a bit.")
        return

    # Check if LeetCode is linked
    link = await db.get_linked_account(user_id)
    if not link or not link["verified"]:
        await message.reply(f"⚠️ You must link and verify your LeetCode account first using {html.code('/link <username>')}!", parse_mode="HTML")
        return

    leetcode_username = link["leetcode_username"]

    # Manual logging: /solved <problem_query> <quality>
    if command.args:
        parts = command.args.split()
        if len(parts) >= 2:
            try:
                quality = int(parts[-1])
                if not (0 <= quality <= 5):
                    raise ValueError()
            except ValueError:
                await message.reply("⚠️ Quality must be an integer between 0 and 5.")
                return

            problem_query = " ".join(parts[:-1]).strip()
            status_msg = await message.reply(f"⏳ Searching LeetCode for '{problem_query}'...")

            # Resolve query using fuzzy/number search resolver
            matches = await leetcode_client.resolve_problem_query(problem_query)
            if not matches:
                await status_msg.edit_text(f"❌ Could not find any problems matching '{problem_query}'.")
                return

            # Filter matches to only solved ones
            solved_matches = await filter_solved_problems(user_id, leetcode_username, matches)
            if not solved_matches:
                await status_msg.edit_text(
                    f"❌ You have not solved this problem yet on LeetCode. "
                    f"It was not found in our database history or your last 20 accepted submissions. "
                    f"If you solved it earlier, please re-submit the problem on LeetCode once again, and then retry this command."
                )
                return

            if len(solved_matches) == 1:
                # Exact match
                problem = solved_matches[0]
                problem_slug = problem["titleSlug"]
                problem_title = problem["title"]
                
                # Retrieve full details for difficulty if missing
                difficulty = problem.get("difficulty")
                if not difficulty:
                    full_details = await leetcode_client.get_problem_details(problem_slug)
                    difficulty = full_details["difficulty"] if full_details else "Medium"
                
                await status_msg.delete()
                await log_and_send_srs_success(message, user_id, problem_slug, problem_title, difficulty, quality)
                return

            # Multiple matches - show selection menu (only showing solved ones)
            await status_msg.delete()
            # Cache the matches and quality rating in Redis
            cache_data = {"quality": quality, "matches": solved_matches}
            cache_key = f"solved_search:{user_id}"
            await cache_manager.set(cache_key, cache_data, expire_seconds=600)

            keyboard_buttons = []
            for idx, q in enumerate(solved_matches[:5]):
                button_text = f"🏆 {q.get('frontendQuestionId', '')}. {q['title']}"
                keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"solved_select:{idx}")])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            await message.reply(
                f"🔍 Multiple matching problems found for '{problem_query}'. "
                f"Please select one you have solved to log with rating {quality}/5:",
                reply_markup=keyboard
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

    # Build keyboard showing problem numbers and titles
    keyboard_buttons = []
    for idx, sub in enumerate(submissions):
        num_prefix = f"{sub.get('frontendQuestionId')}. " if sub.get('frontendQuestionId') else ""
        button_text = f"🏆 {num_prefix}{sub['title']}"
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

    await log_and_send_srs_success(callback_query, user_id, problem_slug, problem_title, difficulty, quality)
    await callback_query.answer("Review Logged!")


@router.callback_query(F.data.startswith("solved_select:"))
async def process_solved_select(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    idx = int(callback_query.data.split(":")[1])

    # Retrieve cached quality and matches
    cache_key = f"solved_search:{user_id}"
    cache_data = await cache_manager.get(cache_key)

    if not cache_data or idx >= len(cache_data.get("matches", [])):
        await callback_query.answer("⚠️ Session expired. Please run /solved <problem> <quality> again.", show_alert=True)
        return

    quality = cache_data["quality"]
    selected_prob = cache_data["matches"][idx]
    problem_slug = selected_prob["titleSlug"]
    problem_title = selected_prob["title"]

    await callback_query.message.edit_text("⏳ Processing review scheduling...")

    # Fetch full details for difficulty if missing
    difficulty = selected_prob.get("difficulty")
    if not difficulty:
        full_details = await leetcode_client.get_problem_details(problem_slug)
        difficulty = full_details["difficulty"] if full_details else "Medium"

    await log_and_send_srs_success(callback_query, user_id, problem_slug, problem_title, difficulty, quality)
    await callback_query.answer("Review Logged!")


@router.message(Command("rm_srs"))
async def cmd_rm_srs(message: Message, command: CommandObject):
    user_id = message.from_user.id
    if await cache_manager.is_rate_limited(user_id, "rm_srs", limit=5, period=10):
        await message.reply("Please wait a moment.")
        return

    if not command.args:
        await message.reply(
            "❌ Please specify a problem to remove from SRS.\n\n"
            "Usage: `/rm_srs <problem_number_or_title>`\n"
            "Examples:\n"
            "• `/rm_srs 1`\n"
            "• `/rm_srs two sum`\n"
            "• `/rm_srs sum` (fuzzy list)",
            parse_mode="Markdown"
        )
        return

    query = command.args.strip()
    status_msg = await message.reply(f"⏳ Searching active SRS reviews for '{query}'...")

    try:
        # Resolve query using fuzzy/number search resolver
        matches = await leetcode_client.resolve_problem_query(query)
        if not matches:
            await status_msg.edit_text(f"❌ Could not find any problems matching '{query}'.")
            return

        # Fetch active reviews in SRS for this user to filter matches
        reviews = await db.get_user_srs_reviews(user_id)
        active_slugs = {r["problem_slug"] for r in reviews}

        # Filter matches to only those in the user's active reviews
        active_matches = [m for m in matches if m["titleSlug"] in active_slugs]

        if not active_matches:
            await status_msg.edit_text(f"❌ You do not have any active SRS reviews matching '{query}'.")
            return

        if len(active_matches) == 1:
            problem = active_matches[0]
            problem_slug = problem["titleSlug"]
            problem_title = problem["title"]
            deleted = await db.delete_srs_review(user_id, problem_slug)
            await status_msg.delete()
            if deleted:
                await message.reply(f"🗑️ {html.bold(problem_title)} has been successfully removed from your SRS reviews.", parse_mode="HTML")
            else:
                await message.reply(f"❌ Failed to remove {problem_title} from SRS.")
            return

        # Multiple matches in active reviews - show selection menu
        await status_msg.delete()
        keyboard_buttons = []
        for q in active_matches[:5]:
            button_text = f"🗑️ {q.get('frontendQuestionId', '')}. {q['title']}"
            keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"srs_rm_select:{q['titleSlug']}")])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        await message.reply(
            f"🔍 Multiple active reviews found for '{query}'. Please select one to remove:",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Error in rm_srs command: {e}", exc_info=True)
        await status_msg.edit_text("❌ An unexpected error occurred. Please try again.")


@router.callback_query(F.data.startswith("srs_rm_select:"))
async def process_srs_rm_select(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    problem_slug = callback_query.data.split(":")[1]

    # Resolve title from user's active reviews to show in confirmation message
    reviews = await db.get_user_srs_reviews(user_id)
    review_item = next((r for r in reviews if r["problem_slug"] == problem_slug), None)
    problem_title = review_item["problem_title"] if review_item else problem_slug

    deleted = await db.delete_srs_review(user_id, problem_slug)
    if deleted:
        await callback_query.message.edit_text(
            f"🗑️ {html.bold(problem_title)} has been successfully removed from your SRS reviews.",
            parse_mode="HTML"
        )
        await callback_query.answer("Problem removed from SRS!")
    else:
        await callback_query.answer("❌ Failed to remove problem.", show_alert=True)
