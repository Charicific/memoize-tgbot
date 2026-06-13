import random
import logging
import datetime
from aiogram import Router, html
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
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

    await message.reply("🔍 Fetching today's LeetCode daily challenge...")

    daily = await leetcode_client.get_daily_challenge()
    if not daily:
        await message.reply("❌ Failed to fetch daily challenge. Please try again later.")
        return

    question = daily["question"]
    title = question["title"]
    title_slug = question["titleSlug"]
    difficulty = question["difficulty"]
    content = question["content"]
    tags = [t["name"] for t in question["topicTags"]]
    link = f"https://leetcode.com{daily['link']}"

    clean_description = clean_leetcode_html(content)
    # Truncate long descriptions to fit Telegram message limit (4096 chars)
    if len(clean_description) > 2000:
        clean_description = clean_description[:2000] + "\n\n...[Description truncated. Click the link to read more]..."

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

    # Cache daily challenge for 2 hours (daily challenges change once a day)
    await cache_manager.set(cache_key, response, expire_seconds=7200)
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

    await message.reply("🔍 Searching for a matching problem... Please wait.")

    # Fetch problemset questions
    questions = await leetcode_client.get_problemset_questions(limit=100, difficulty=difficulty, tag_slug=tag)
    
    # Filter out paid only questions
    free_questions = [q for q in questions if not q.get("isPaidOnly")]
    
    if not free_questions:
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
    
    await message.reply(response, parse_mode="HTML", disable_web_page_preview=True)
