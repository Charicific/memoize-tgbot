import random
import logging
import datetime
from aiogram import Router, html, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from src.services.leetcode import LeetCodeClient
from src.services.redis_cache import cache_manager
from src.utils.formatters import clean_leetcode_html

router = Router()
logger = logging.getLogger(__name__)

# Reusable client instanced locally or dynamically
leetcode_client = LeetCodeClient()

@router.message(Command("daily"))
async def cmd_daily(message: Message):
    user_id = message.from_user.id
    if await cache_manager.is_rate_limited(user_id, "daily", limit=3, period=10):
        await message.reply("Please don't spam the daily challenge command.")
        return

    # Check cache first
    cache_key = "daily_challenge"
    cached = await cache_manager.get(cache_key)
    
    if cached:
        await message.reply(cached, parse_mode="HTML", disable_web_page_preview=True)
        return

    status_msg = await message.reply("🔍 Fetching today's LeetCode daily challenge...")

    daily = await leetcode_client.get_daily_challenge()
    if not daily:
        try:
            await status_msg.delete()
        except Exception:
            pass
        await message.reply("❌ Failed to fetch daily challenge. Please try again later.")
        return

    question = daily["question"]
    title = question["title"]
    frontend_id = question.get("questionFrontendId", "")
    title_slug = question["titleSlug"]
    difficulty = question["difficulty"]
    content = question["content"]
    tags = [t["name"] for t in question["topicTags"]]
    link = f"https://leetcode.com{daily['link']}"

    clean_description = clean_leetcode_html(content, max_length=2000)

    diff_emoji = "🟢" if difficulty == "Easy" else "🟡" if difficulty == "Medium" else "🔴"
    
    title_display = f"{frontend_id}. {title}" if frontend_id else title
    response = (
        f"📅 {html.bold('Daily Coding Challenge')} ({daily['date']})\n\n"
        f"🏆 {html.bold(title_display)}\n"
        f"Difficulty: {diff_emoji} {html.bold(difficulty)}\n"
        f"Tags: {html.italic(', '.join(tags))}\n"
        f"🔗 Link: <a href='{link}'>Solve on LeetCode</a>\n\n"
        f"{html.bold('Problem Description:')}\n"
        f"{clean_description}\n\n"
        f"💡 {html.italic('To get progressive hints for this problem, type:')}\n"
        f"`/hint {title_slug}`"
    )

    # Cache daily challenge for 2 hours (daily challenges change once a day)
    await cache_manager.set(cache_key, response, expire_seconds=7200)
    try:
        await status_msg.delete()
    except Exception:
        pass
    await message.reply(response, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("contest"))
async def cmd_contest(message: Message):
    user_id = message.from_user.id
    if await cache_manager.is_rate_limited(user_id, "contest", limit=3, period=10):
        await message.reply("Please wait a moment.")
        return

    # Check cache
    cache_key = "contests_list"
    cached = await cache_manager.get(cache_key)
    if cached:
        await message.reply(cached, parse_mode="HTML", disable_web_page_preview=True)
        return

    contests = await leetcode_client.get_contests()
    if not contests:
        await message.reply("❌ Could not fetch contest schedule.")
        return

    now_ts = datetime.datetime.now().timestamp()
    upcoming = []
    
    for c in contests:
        start_time = int(c["startTime"])
        # Only list future contests
        if start_time > now_ts:
            upcoming.append(c)

    # Sort by start time ascending
    upcoming.sort(key=lambda x: int(x["startTime"]))

    if not upcoming:
        await message.reply("🏁 No upcoming contests found.")
        return

    response = f"📅 {html.bold('Upcoming LeetCode Contests:')}\n\n"
    for c in upcoming[:4]: # Show next 4 contests
        start_dt = datetime.datetime.fromtimestamp(int(c["startTime"]), tz=datetime.timezone.utc)
        duration_mins = int(c["duration"]) // 60
        delta = start_dt - datetime.datetime.now(datetime.timezone.utc)
        
        # Format delta
        days = delta.days
        hours = delta.seconds // 3600
        mins = (delta.seconds % 3600) // 60
        
        countdown = ""
        if days > 0:
            countdown += f"{days}d "
        countdown += f"{hours}h {mins}m"

        response += (
            f"🏆 {html.bold(c['title'])}\n"
            f"• Starts in: {html.code(countdown)}\n"
            f"• Start Time: {start_dt.strftime('%d %b %Y, %I:%M %p UTC')}\n"
            f"• Duration: {duration_mins} minutes\n"
            f"• Link: <a href='https://leetcode.com/contest/{c['titleSlug']}'>Register Here</a>\n\n"
        )

    # Cache for 1 hour
    await cache_manager.set(cache_key, response, expire_seconds=3600)
    await message.reply(response, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("random"))
async def cmd_random(message: Message, command: CommandObject):
    user_id = message.from_user.id
    if await cache_manager.is_rate_limited(user_id, "random", limit=5, period=10):
        await message.reply("Too many random requests. Wait a bit.")
        return

    difficulty = None
    tag = None
    
    if command.args:
        args = command.args.split()
        for arg in args:
            arg_lower = arg.lower()
            if arg_lower in ["easy", "medium", "hard"]:
                difficulty = arg_lower
            else:
                tag = arg_lower

    status_msg = await message.reply("🔍 Searching for a matching problem... Please wait.")

    # Fetch problemset questions
    questions = await leetcode_client.get_problemset_questions(limit=100, difficulty=difficulty, tag_slug=tag)
    
    # Filter out paid only questions
    free_questions = [q for q in questions if not q.get("isPaidOnly")]
    
    if not free_questions:
        try:
            await status_msg.delete()
        except Exception:
            pass
        await message.reply("❌ No matching free questions found. Try changing the filters.")
        return

    # Pick a random one
    q = random.choice(free_questions)
    
    diff_emoji = "🟢" if q['difficulty'] == "Easy" else "🟡" if q['difficulty'] == "Medium" else "🔴"
    
    response = (
        f"🎯 {html.bold('Random LeetCode Problem')}\n\n"
        f"🏆 {html.bold(q['title'])}\n"
        f"Frontend ID: #{q['frontendQuestionId']}\n"
        f"Difficulty: {diff_emoji} {html.bold(q['difficulty'])}\n"
        f"🔗 Link: <a href='https://leetcode.com/problems/{q['titleSlug']}'>Solve Problem</a>\n\n"
        f"💡 {html.italic('To get progressive hints for this problem, type:')}\n"
        f"`/hint {q['titleSlug']}`"
    )
    
    try:
        await status_msg.delete()
    except Exception:
        pass
    await message.reply(response, parse_mode="HTML", disable_web_page_preview=True)


@router.callback_query(F.data == "view_daily_desc")
async def process_view_daily_desc(callback_query: CallbackQuery):
    # Fetch today's daily challenge
    daily = await leetcode_client.get_daily_challenge()
    if not daily:
        await callback_query.answer("❌ Failed to fetch daily challenge details. Please try again later.", show_alert=True)
        return
        
    question = daily["question"]
    title = question["title"]
    title_slug = question["titleSlug"]
    difficulty = question["difficulty"]
    content = question["content"]
    tags = [t["name"] for t in question["topicTags"]]
    link = f"https://leetcode.com{daily['link']}"

    clean_description = clean_leetcode_html(content, max_length=2000)
    diff_emoji = "🟢" if difficulty == "Easy" else "🟡" if difficulty == "Medium" else "🔴"
    
    response = (
        f"📅 {html.bold('Daily Coding Challenge')} ({daily['date']})\n\n"
        f"🏆 {html.bold(title)}\n"
        f"Difficulty: {diff_emoji} {html.bold(difficulty)}\n"
        f"Tags: {html.italic(', '.join(tags))}\n"
        f"🔗 Link: <a href='{link}'>Solve on LeetCode</a>\n\n"
        f"{html.bold('Problem Description:')}\n"
        f"{clean_description}\n\n"
        f"💡 {html.italic('To get progressive hints for this problem, type:')}\n"
        f"`/hint {title_slug}`"
    )

    try:
        await callback_query.message.edit_text(response, parse_mode="HTML", disable_web_page_preview=True)
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Error editing daily challenge DM reminder description: {e}")
        await callback_query.answer("Failed to display description.")


def format_problem_solve_message(details: dict) -> str:
    title = details.get("title", "")
    q_num = details.get("questionFrontendId", "")
    difficulty = details.get("difficulty", "Medium")
    title_slug = details.get("titleSlug", "")
    content = details.get("content") or "No description available."
    tags = [t["name"] for t in details.get("topicTags", [])]
    link = f"https://leetcode.com/problems/{title_slug}"
    
    clean_description = clean_leetcode_html(content, max_length=2000)
    diff_emoji = "🟢" if difficulty == "Easy" else "🟡" if difficulty == "Medium" else "🔴"
    title_display = f"{q_num}. {title}" if q_num else title
    
    response = (
        f"🏆 {html.bold(title_display)}\n"
        f"Difficulty: {diff_emoji} {html.bold(difficulty)}\n"
        f"Tags: {html.italic(', '.join(tags)) if tags else 'None'}\n"
        f"🔗 Link: <a href='{link}'>Solve on LeetCode</a>\n\n"
        f"{html.bold('Problem Description:')}\n"
        f"{clean_description}\n\n"
        f"💡 {html.italic('To get progressive hints for this problem, type:')}\n"
        f"`/hint {title_slug}`"
    )
    return response


@router.message(Command("solve"))
async def cmd_solve(message: Message, command: CommandObject):
    user_id = message.from_user.id
    if await cache_manager.is_rate_limited(user_id, "solve", limit=5, period=10):
        await message.reply("Please don't spam the /solve command.")
        return

    if not command.args:
        await message.reply(
            "❌ Please specify a problem to solve.\n\n"
            "Usage: `/solve <problem_number_or_title>`\n"
            "Examples:\n"
            "• `/solve 1`\n"
            "• `/solve two sum`\n"
            "• `/solve sum` (fuzzy list)",
            parse_mode="Markdown"
        )
        return

    query = command.args.strip()
    status_msg = await message.reply(f"🤖 Searching LeetCode for problem '{query}'...")

    try:
        matches = await leetcode_client.resolve_problem_query(query)
        if not matches:
            await status_msg.edit_text(f"❌ Could not find any problems matching '{query}'.")
            return

        if len(matches) == 1:
            selected_prob = matches[0]
            problem_slug = selected_prob["titleSlug"]
            
            # Fetch full details
            details = await leetcode_client.get_problem_details(problem_slug)
            if not details:
                await status_msg.edit_text("❌ Failed to fetch problem details. Please try again.")
                return

            response = format_problem_solve_message(details)
            link = f"https://leetcode.com/problems/{problem_slug}"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🔗 Solve on LeetCode", url=link)
                ]
            ])
            await status_msg.delete()
            await message.reply(response, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
        else:
            # Save matches to cache for callback selection
            context = {
                "problems": matches[:5]
            }
            await cache_manager.set(f"solve_search:{user_id}", context, expire_seconds=300)

            keyboard_buttons = []
            for idx, q in enumerate(matches[:5]):
                button_text = f"🏆 {q.get('frontendQuestionId', '')}. {q['title']} ({q.get('difficulty', 'Medium')})"
                keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"solve_select_prob:{idx}")])

            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            await status_msg.edit_text(
                f"🔍 Multiple matching problems found for '{query}'. Please select one to view and solve:",
                reply_markup=keyboard
            )
    except Exception as e:
        logger.error(f"Error in /solve command: {e}", exc_info=True)
        await status_msg.edit_text("❌ An unexpected error occurred while searching. Please try again later.")


@router.callback_query(F.data.startswith("solve_select_prob:"))
async def process_solve_select_prob(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    prob_idx = int(callback_query.data.split(":")[1])

    context = await cache_manager.get(f"solve_search:{user_id}")
    if not context:
        await callback_query.answer("⚠️ Session expired. Please run /solve again.", show_alert=True)
        return

    problems = context.get("problems", [])
    if prob_idx >= len(problems):
        await callback_query.answer("⚠️ Selected problem is invalid.", show_alert=True)
        return

    selected_prob = problems[prob_idx]
    problem_slug = selected_prob["titleSlug"]

    # Delete the cache context
    await cache_manager.delete(f"solve_search:{user_id}")

    try:
        await callback_query.message.edit_text("🔍 Fetching details for the selected problem...")
        
        details = await leetcode_client.get_problem_details(problem_slug)
        if not details:
            await callback_query.message.edit_text("❌ Failed to fetch problem details. Please try again.")
            return

        response = format_problem_solve_message(details)
        link = f"https://leetcode.com/problems/{problem_slug}"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔗 Solve on LeetCode", url=link)
            ]
        ])
        
        await callback_query.message.edit_text(
            response,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Error processing solve select callback: {e}", exc_info=True)
        await callback_query.message.edit_text("❌ An error occurred while fetching details. Please try again.")



