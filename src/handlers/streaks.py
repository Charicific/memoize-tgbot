import datetime
import json
import logging
from html import escape as html_escape
from aiogram import Router, html, F
from aiogram.filters import Command
from aiogram.types import Message

from src.services.supabase_db import db
from src.services.leetcode import LeetCodeClient
from src.services.redis_cache import cache_manager

router = Router()
logger = logging.getLogger(__name__)
leetcode_client = LeetCodeClient()

def calculate_streaks(dates: list[datetime.date]) -> tuple[int, int]:
    """
    Given a list of dates, calculates:
    - current_streak: consecutive days leading up to today (or yesterday if today is not yet solved).
    - longest_streak: the maximum consecutive days sequence.
    """
    if not dates:
        return 0, 0
    
    # Remove duplicates and sort descending
    unique_dates = sorted(list(set(dates)), reverse=True)
    
    today = datetime.datetime.now(datetime.timezone.utc).date()
    yesterday = today - datetime.timedelta(days=1)
    
    current_streak = 0
    if unique_dates[0] == today or unique_dates[0] == yesterday:
        current_streak = 1
        expected_date = unique_dates[0] - datetime.timedelta(days=1)
        for d in unique_dates[1:]:
            if d == expected_date:
                current_streak += 1
                expected_date = d - datetime.timedelta(days=1)
            elif d < expected_date:
                break
    
    longest_streak = 0
    temp_streak = 0
    expected_date = None
    
    # Sort ascending for longest streak calculation
    for d in sorted(unique_dates):
        if expected_date is None or d == expected_date:
            temp_streak += 1
        else:
            if temp_streak > longest_streak:
                longest_streak = temp_streak
            temp_streak = 1
        expected_date = d + datetime.timedelta(days=1)
        
    if temp_streak > longest_streak:
        longest_streak = temp_streak
        
    return current_streak, longest_streak

def parse_leetcode_calendar(calendar_str: str) -> list[datetime.date]:
    """
    Parses LeetCode submissionCalendar string representation (e.g. {"1767225600": 1, ...})
    into a list of datetime.date objects.
    """
    try:
        cal = json.loads(calendar_str)
        dates = []
        for ts_str in cal.keys():
            ts = int(ts_str)
            dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).date()
            dates.append(dt)
        return dates
    except Exception as e:
        logger.error(f"Error parsing LeetCode calendar string: {e}")
        return []

@router.message(Command("streak"))
async def cmd_streak(message: Message):
    user_id = message.from_user.id
    
    if await cache_manager.is_rate_limited(user_id, "streak", limit=5, period=10):
        await message.reply("Too many streak requests. Please wait a bit.")
        return
        
    # Fetch linked account
    link = await db.get_linked_account(user_id)
    if not link or not link["verified"]:
        await message.reply(
            f"⚠️ You must link and verify your LeetCode account first using {html.code('/link &lt;username&gt;')}!", 
            parse_mode="HTML"
        )
        return
        
    leetcode_username = link["leetcode_username"]
    
    # Check cache first
    cache_key = f"streak_stats:{user_id}"
    cached = await cache_manager.get(cache_key)
    if cached:
        await message.reply(cached, parse_mode="HTML")
        return
        
    # Fetch user calendar from LeetCode
    calendar = await leetcode_client.get_user_calendar(leetcode_username)
    if not calendar:
        await message.reply("❌ Could not fetch streak calendar from LeetCode profile. Please try again later.")
        return
        
    cal_str = calendar.get("submissionCalendar") or "{}"
    dates = parse_leetcode_calendar(cal_str)
    
    current_streak, max_streak = calculate_streaks(dates)
    total_active_days = calendar.get("totalActiveDays", 0)
    
    response = (
        f"🔥 {html.bold('LeetCode Submission Streak')} ({html.italic(leetcode_username)}) 🔥\n\n"
        f"📅 {html.bold('Current Streak:')} {html.code(f'{current_streak} days')}\n"
        f"🏆 {html.bold('Max Streak:')} {html.code(f'{max_streak} days')}\n"
        f"🟢 {html.bold('Total Active Days:')} {html.code(f'{total_active_days} days')}\n\n"
        f"Keep coding daily and build consistency! 🚀"
    )
    
    # Cache for 10 minutes
    await cache_manager.set(cache_key, response, expire_seconds=600)
    await message.reply(response, parse_mode="HTML")

@router.message(Command("dstreak"))
async def cmd_dstreak(message: Message):
    user_id = message.from_user.id
    
    if await cache_manager.is_rate_limited(user_id, "dstreak", limit=5, period=10):
        await message.reply("Too many daily challenge streak requests. Please wait a bit.")
        return
        
    # Fetch linked account
    link = await db.get_linked_account(user_id)
    if not link or not link["verified"]:
        await message.reply(
            f"⚠️ You must link and verify your LeetCode account first using {html.code('/link &lt;username&gt;')}!", 
            parse_mode="HTML"
        )
        return
        
    leetcode_username = link["leetcode_username"]
    
    # Fetch daily challenge solve dates from DB
    dates = await db.get_user_daily_challenge_dates(user_id)
    
    current_streak, longest_streak = calculate_streaks(dates)
    
    response = (
        f"🏆 {html.bold('LeetCode Daily Challenge Streak')} ({html.italic(leetcode_username)}) 🏆\n\n"
        f"🔥 {html.bold('Current DCC Streak:')} {html.code(f'{current_streak} days')}\n"
        f"⭐ {html.bold('Longest DCC Streak:')} {html.code(f'{longest_streak} days')}\n\n"
        f"Maintain your discipline and conquer the daily challenges! 💪"
    )
    
    await message.reply(response, parse_mode="HTML")
