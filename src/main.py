import asyncio
import logging
import datetime
import traceback
from typing import Optional, List, Dict, Any
from html import escape as html_escape
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, html, types, BaseMiddleware
from aiogram.exceptions import TelegramBadRequest

from aiogram.types import ErrorEvent, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.redis import RedisStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from src.config import settings
from src.services.supabase_db import db
from src.services.redis_cache import cache_manager
from src.services.leetcode import LeetCodeClient
from src.handlers import get_main_router
from src.utils.formatters import clean_leetcode_html
from src.middlewares.ban_middleware import BanCheckMiddleware
from src.middlewares.maintenance_middleware import MaintenanceCheckMiddleware
from src.middlewares.dot_command_middleware import DotCommandMiddleware


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize clients
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher(storage=cache_manager.fsm_storage)
leetcode_client = LeetCodeClient()


class GroupMemberMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, types.Message) and event.chat.type in [
            "group",
            "supergroup",
        ]:
            user = event.from_user
            if user:
                # Skip Telegram's service account and any bots
                if user.id == 777000 or user.is_bot:
                    return await handler(event, data)
                try:
                    await db.record_group_member(
                        group_id=event.chat.id,
                        telegram_id=user.id,
                        username=user.username,
                        first_name=user.first_name,
                    )
                except Exception as e:
                    logger.error(f"Error in GroupMemberMiddleware: {e}")
        return await handler(event, data)


dp.message.outer_middleware(DotCommandMiddleware())
dp.message.outer_middleware(GroupMemberMiddleware())
dp.message.outer_middleware(BanCheckMiddleware())
dp.message.outer_middleware(MaintenanceCheckMiddleware())
dp.callback_query.outer_middleware(BanCheckMiddleware())
dp.callback_query.outer_middleware(MaintenanceCheckMiddleware())


# Initialize Scheduler
# SQLAlchemyJobStore persists jobs into Postgres so they survive restarts
jobstores = {
    "default": SQLAlchemyJobStore(
        url=settings.SUPABASE_DB_URL.replace("postgresql+asyncpg://", "postgresql://")
    )
}
scheduler = AsyncIOScheduler(
    jobstores=jobstores,
    job_defaults={"misfire_grace_time": 60}
)


def stable_hash(s: str) -> int:
    import hashlib
    return int(hashlib.md5(s.encode('utf-8')).hexdigest(), 16)


class UnifiedPollingCache:
    def __init__(self):
        self.submissions = {}
        self.lock = asyncio.Lock()

    async def get_submissions(self, username: str) -> List[Dict[str, Any]]:
        async with self.lock:
            if username in self.submissions:
                return self.submissions[username]
            try:
                await asyncio.sleep(0.1)
                subs = await leetcode_client.get_recent_accepted_submissions(username, limit=5)
                self.submissions[username] = subs
                return subs
            except Exception as e:
                logger.error(f"Error fetching submissions for {username}: {e}")
                self.submissions[username] = []
                return []


async def poll_all_active_battles():
    """
    Combined background job to poll both active 1v1 and group battles.
    Runs every 30 seconds.
    """
    logger.info("Running unified active battles polling cycle...")
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        current_tick = int(now.timestamp() / 30)

        active_1v1 = await db.get_active_battles()
        active_group = await db.get_active_group_battles()

        due_1v1_battles = []
        due_group_battles = []
        telegram_ids_to_resolve = set()

        group_participants_map = {}

        # 1. Process 1v1 battles timeouts and categorize active ones
        for battle in active_1v1:
            expires_at = battle["expires_at"]
            if isinstance(expires_at, str):
                expires_at = datetime.datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            elif expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)

            # Handle expiry immediately
            if now > expires_at:
                await db.update_battle_status(battle["id"], "EXPIRED")
                chat_id = battle.get("chat_id")
                group_info = ""
                if chat_id:
                    if chat_id < 0:
                        try:
                            chat = await bot.get_chat(chat_id)
                            group_title = chat.title or "Group"
                            group_username = chat.username
                        except Exception as chat_err:
                            logger.error(f"Error fetching chat info for group {chat_id}: {chat_err}")
                            group_title = "Group"
                            group_username = None
                            
                        msg_id = battle.get("message_id")
                        link = ""
                        if msg_id:
                            if group_username:
                                link = f"https://t.me/{group_username}/{msg_id}"
                            elif str(chat_id).startswith("-100"):
                                link = f"https://t.me/c/{str(chat_id)[4:]}/{msg_id}"
                                
                        if link:
                            group_info = f"\n• {html.bold('Group:')} <a href='{link}'>{group_title}</a>"
                        elif group_username:
                            group_info = f"\n• {html.bold('Group:')} {group_title} (@{group_username})"
                        else:
                            group_info = f"\n• {html.bold('Group:')} {group_title} ({chat_id})"
                    else:
                        group_info = f"\n• {html.bold('Group:')} Private DM"

                log_text = (
                    f"⏱️ {html.bold('LeetCode Battle Expired')} ⏱️\n\n"
                    f"• {html.bold('Battle ID:')} {html.code(str(battle['id']))}\n"
                    f"• {html.bold('Problem:')} {battle['problem_title']}\n"
                    f"• {html.bold('Players:')} <a href='tg://user?id={battle['challenger_id']}'>Challenger</a> and <a href='tg://user?id={battle['opponent_id']}'>Opponent</a>"
                    f"{group_info}"
                )
                await send_log(log_text, disable_notification=True)
                expired_msg = f"⏱️ Battle for {html.bold(battle['problem_title'])} has expired because time limit was reached."
                try:
                    await bot.send_message(chat_id=battle["challenger_id"], text=expired_msg, parse_mode="HTML")
                    await bot.send_message(chat_id=battle["opponent_id"], text=expired_msg, parse_mode="HTML")
                except Exception as e:
                    logger.error(f"Error sending battle expiration notification: {e}")
                continue

            if battle["status"] != "ACTIVE":
                continue

            remaining_seconds = (expires_at - now).total_seconds()
            is_due = False
            b_hash = stable_hash(str(battle["id"]))

            if remaining_seconds > 600:
                is_due = (current_tick + b_hash) % 20 == 0
            elif 300 < remaining_seconds <= 600:
                is_due = (current_tick + b_hash) % 4 == 0
            elif 120 < remaining_seconds <= 300:
                is_due = (current_tick + b_hash) % 2 == 0
            else:
                is_due = True

            if is_due:
                due_1v1_battles.append(battle)
                telegram_ids_to_resolve.add(battle["challenger_id"])
                telegram_ids_to_resolve.add(battle["opponent_id"])

        # 2. Process Group battles timeouts and categorize active ones
        for battle in active_group:
            battle_id = str(battle["id"])
            group_id = battle["group_id"]

            expires_at = battle["expires_at"]
            if isinstance(expires_at, str):
                expires_at = datetime.datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            elif expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)

            # Handle PENDING battles expiration (5 minutes timeout if never started)
            if battle["status"] == "PENDING":
                created_at = battle["created_at"]
                if isinstance(created_at, str):
                    created_at = datetime.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                elif created_at and created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=datetime.timezone.utc)
                
                if now > (created_at + datetime.timedelta(minutes=5)):
                    await db.update_group_battle_status(battle_id, "CANCELLED")
                    try:
                        await bot.send_message(
                            chat_id=group_id,
                            text=f"⏳ The Group Battle challenge for {html.bold(battle['problem_title'])} has been cancelled because it was not started within 5 minutes.",
                            parse_mode="HTML"
                        )
                    except Exception as msg_err:
                        logger.error(f"Error sending group battle cancellation: {msg_err}")
                continue

            # Check expiration for ACTIVE battles
            if now > expires_at and battle["status"] == "ACTIVE":
                await db.update_group_battle_status(battle_id, "COMPLETED")
                participants = await db.get_group_battle_participants(battle_id)
                await end_group_battle(battle, participants, expired=True)
                continue

            if battle["status"] != "ACTIVE":
                continue

            remaining_seconds = (expires_at - now).total_seconds()
            is_due = False
            b_hash = stable_hash(battle_id)

            if remaining_seconds > 600:
                is_due = (current_tick + b_hash) % 20 == 0
            elif 300 < remaining_seconds <= 600:
                is_due = (current_tick + b_hash) % 4 == 0
            elif 120 < remaining_seconds <= 300:
                is_due = (current_tick + b_hash) % 2 == 0
            else:
                is_due = True

            if is_due:
                participants = await db.get_group_battle_participants(battle_id)
                if not participants:
                    continue
                group_participants_map[battle_id] = participants
                due_group_battles.append(battle)
                for p in participants:
                    if p["solved_at"] is None:
                        telegram_ids_to_resolve.add(p["telegram_id"])

        if not due_1v1_battles and not due_group_battles:
            return

        # 3. Batch resolve LeetCode usernames
        user_to_leetcode = await db.get_verified_links_for_users(list(telegram_ids_to_resolve))

        # 4. Fetch submissions with shared cache to deduplicate
        shared_cache = UnifiedPollingCache()

        async def check_1v1_battle_jittered(battle):
            battle_id = str(battle["id"])
            jitter_delay = stable_hash(battle_id) % 20
            await asyncio.sleep(jitter_delay)

            fresh_battle = await db.get_battle(battle_id)
            if not fresh_battle or fresh_battle["status"] != "ACTIVE":
                return

            c_id = fresh_battle["challenger_id"]
            o_id = fresh_battle["opponent_id"]
            c_user = user_to_leetcode.get(c_id)
            o_user = user_to_leetcode.get(o_id)

            if not c_user or not o_user:
                return

            c_subs, o_subs = await asyncio.gather(
                shared_cache.get_submissions(c_user),
                shared_cache.get_submissions(o_user)
            )

            started_at = fresh_battle["started_at"]
            if isinstance(started_at, str):
                started_at = datetime.datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            elif started_at and started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=datetime.timezone.utc)

            c_solved_ts = None
            o_solved_ts = None

            for sub in c_subs:
                if sub["titleSlug"] == fresh_battle["problem_slug"]:
                    sub_time = datetime.datetime.fromtimestamp(int(sub["timestamp"]), tz=datetime.timezone.utc)
                    if sub_time > started_at:
                        c_solved_ts = sub_time
                        break

            for sub in o_subs:
                if sub["titleSlug"] == fresh_battle["problem_slug"]:
                    sub_time = datetime.datetime.fromtimestamp(int(sub["timestamp"]), tz=datetime.timezone.utc)
                    if sub_time > started_at:
                        o_solved_ts = sub_time
                        break

            winner_id = None
            loser_id = None

            if c_solved_ts and o_solved_ts:
                if c_solved_ts < o_solved_ts:
                    winner_id = c_id
                    loser_id = o_id
                else:
                    winner_id = o_id
                    loser_id = c_id
            elif c_solved_ts:
                winner_id = c_id
                loser_id = o_id
            elif o_solved_ts:
                winner_id = o_id
                loser_id = c_id

            if winner_id:
                now_ended = datetime.datetime.now(datetime.timezone.utc)
                await db.update_battle_status(battle_id, "COMPLETED", winner_id=winner_id, ended_at=now_ended)
                await db.add_xp_coins(winner_id, xp=100, coins=20)
                await db.add_xp_coins(loser_id, xp=20, coins=0)

                winner_row = await db.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", winner_id)
                loser_row = await db.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", loser_id)
                w_name = winner_row["first_name"] or winner_row["username"] or "Winner"
                l_name = loser_row["first_name"] or loser_row["username"] or "Loser"

                from src.utils.logging_helper import send_log
                chat_id = fresh_battle.get("chat_id")
                group_info = ""
                if chat_id:
                    if chat_id < 0:
                        try:
                            chat = await bot.get_chat(chat_id)
                            group_title = chat.title or "Group"
                            group_username = chat.username
                        except Exception as chat_err:
                            logger.error(f"Error fetching chat info for group {chat_id}: {chat_err}")
                            group_title = "Group"
                            group_username = None
                            
                        msg_id = fresh_battle.get("message_id")
                        link = ""
                        if msg_id:
                            if group_username:
                                link = f"https://t.me/{group_username}/{msg_id}"
                            elif str(chat_id).startswith("-100"):
                                link = f"https://t.me/c/{str(chat_id)[4:]}/{msg_id}"
                                
                        if link:
                            group_info = f"\n• {html.bold('Group:')} <a href='{link}'>{group_title}</a>"
                        elif group_username:
                            group_info = f"\n• {html.bold('Group:')} {group_title} (@{group_username})"
                        else:
                            group_info = f"\n• {html.bold('Group:')} {group_title} ({chat_id})"
                    else:
                        group_info = f"\n• {html.bold('Group:')} Private DM"

                log_text = (
                    f"🏆 {html.bold('LeetCode Battle Won')} 🏆\n\n"
                    f"• {html.bold('Battle ID:')} {html.code(battle_id)}\n"
                    f"• {html.bold('Problem:')} {fresh_battle['problem_title']}\n"
                    f"• {html.bold('Winner:')} {w_name} ({winner_id})\n"
                    f"• {html.bold('Loser:')} {l_name} ({loser_id})"
                    f"{group_info}"
                )
                await send_log(log_text, disable_notification=True)

                winner_url = f"https://leetcode.com/problems/{fresh_battle['problem_slug']}"
                result_msg = (
                    f"🎉 {html.bold('LeetCode Battle Completed!')} 🎉\n\n"
                    f"🏆 Problem: <a href='{winner_url}'>{fresh_battle['problem_title']}</a>\n"
                    f"🥇 Winner: {html.bold(w_name)} (Awarded 100 XP, 20 coins)\n"
                    f"🥈 Loser: {html.bold(l_name)} (Awarded 20 XP)\n\n"
                    f"Congratulations to both players for competing!"
                )

                try:
                    await bot.send_message(chat_id=c_id, text=result_msg, parse_mode="HTML", disable_web_page_preview=True)
                    await bot.send_message(chat_id=o_id, text=result_msg, parse_mode="HTML", disable_web_page_preview=True)
                except Exception as e:
                    logger.error(f"Error sending battle completed message: {e}")

        async def check_group_battle_jittered(battle):
            battle_id = str(battle["id"])
            group_id = battle["group_id"]
            jitter_delay = stable_hash(battle_id) % 20
            await asyncio.sleep(jitter_delay)

            fresh_battle = await db.get_group_battle(battle_id)
            if not fresh_battle or fresh_battle["status"] != "ACTIVE":
                return

            starts_at = fresh_battle["starts_at"]
            if isinstance(starts_at, str):
                starts_at = datetime.datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
            elif starts_at and starts_at.tzinfo is None:
                starts_at = starts_at.replace(tzinfo=datetime.timezone.utc)

            participants = group_participants_map.get(battle_id)
            if not participants:
                return

            solves_updated = False
            for p in participants:
                if p["solved_at"] is not None:
                    continue

                leetcode_user = user_to_leetcode.get(p["telegram_id"])
                if not leetcode_user:
                    continue

                subs = await shared_cache.get_submissions(leetcode_user)
                for sub in subs:
                    if sub["titleSlug"] == fresh_battle["problem_slug"]:
                        sub_time = datetime.datetime.fromtimestamp(int(sub["timestamp"]), tz=datetime.timezone.utc)
                        if sub_time > starts_at:
                            solve_time = int((sub_time - starts_at).total_seconds())
                            await db.update_group_participant_solve(battle_id, p["telegram_id"], sub_time, solve_time)
                            p["solved_at"] = sub_time
                            p["solve_time_seconds"] = solve_time
                            solves_updated = True

                            solved_msg = (
                                f"🎉 {html.bold('LeetCode Group Battle Solve!')} 🏆\n\n"
                                f"• Player: <a href='tg://user?id={p['telegram_id']}'>{p['first_name'] or p['username']}</a>\n"
                                f"• Problem: {fresh_battle['problem_title']}\n"
                                f"• Time Taken: {solve_time // 60}m {solve_time % 60}s\n\n"
                                f"Great job! Keep it up! 💪"
                            )
                            try:
                                await bot.send_message(chat_id=group_id, text=solved_msg, parse_mode="HTML")
                            except Exception as e:
                                logger.error(f"Error sending group solve notification: {e}")
                            break

            participants_fresh = await db.get_group_battle_participants(battle_id)
            all_solved = all(p["solved_at"] is not None for p in participants_fresh)
            if all_solved and solves_updated:
                await db.update_group_battle_status(battle_id, "COMPLETED")
                await end_group_battle(fresh_battle, participants_fresh, expired=False)

        tasks = []
        for battle in due_1v1_battles:
            tasks.append(check_1v1_battle_jittered(battle))
        for battle in due_group_battles:
            tasks.append(check_group_battle_jittered(battle))

        await asyncio.gather(*tasks)

    except Exception as e:
        logger.error(f"Error in poll_all_active_battles: {e}", exc_info=True)
        tb = traceback.format_exc()
        if len(tb) > 2500:
            tb = tb[:2500] + "\n...[truncated]"
        error_msg = (
            f"🚨 {html.bold('CRITICAL: Error in Background Task (poll_all_active_battles)')} 🚨\n\n"
            f"⚠️ {html.bold('Error:')} {html.code(str(e))}\n\n"
            f"📂 {html.bold('Traceback:')}\n<pre><code class='language-python'>{html_escape(tb)}</code></pre>"
        )
        from src.utils.logging_helper import send_log
        await send_log(error_msg, pin=True, disable_notification=False)


async def end_group_battle(battle, participants, expired: bool):
    battle_id = str(battle["id"])
    group_id = battle["group_id"]
    
    # Sort: those who solved first, then unsolved
    solved_players = [p for p in participants if p["solved_at"] is not None]
    unsolved_players = [p for p in participants if p["solved_at"] is None]
    
    solved_players.sort(key=lambda x: x["solve_time_seconds"] or 999999)
    unsolved_players.sort(key=lambda x: x["joined_at"])
    
    final_ranking = solved_players + unsolved_players
    
    leaderboard_text = f"🏁 {html.bold('Group Battle Ended!')} 🏁\n\n"
    if expired:
        leaderboard_text += "⏱️ Time limit of 60 minutes reached!\n\n"
    else:
        leaderboard_text += "🎉 All participants completed the challenge!\n\n"
        
    leaderboard_text += f"🏆 Problem: {battle['problem_title']} ({battle['difficulty']})\n\n"
    leaderboard_text += f"👥 {html.bold('Final Battle Leaderboard:')}\n"
    
    for rank, p in enumerate(final_ranking, start=1):
        name = p["first_name"] or p["username"] or f"User {p['telegram_id']}"
        if p["solved_at"] is not None:
            time_str = f"{p['solve_time_seconds'] // 60}m {p['solve_time_seconds'] % 60}s"
            status_str = f"✅ Solved in {time_str}"
            
            # Distribute rewards based on rank
            if rank == 1:
                xp, coins = 150, 30
                medal = "🥇"
            elif rank == 2:
                xp, coins = 100, 20
                medal = "🥈"
            elif rank == 3:
                xp, coins = 75, 15
                medal = "🥉"
            else:
                xp, coins = 50, 10
                medal = "🎖️"
        else:
            status_str = "❌ Unsolved"
            xp, coins = 10, 0
            medal = "⚫"
            
        try:
            await db.add_xp_coins(p["telegram_id"], xp=xp, coins=coins)
        except Exception as add_err:
            logger.error(f"Error adding XP/coins in end_group_battle for {p['telegram_id']}: {add_err}")
            
        leaderboard_text += f"{medal} {rank}. {html.bold(name)} — {status_str} (Awarded +{xp} XP, +{coins} coins)\n"

    try:
        await bot.send_message(chat_id=group_id, text=leaderboard_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error sending final group battle leaderboard: {e}")
        
    # Log battle completed/expired to log channel
    try:
        title = 'Group LeetCode Battle Expired' if expired else 'Group LeetCode Battle Completed'
        emoji = '⏱️' if expired else '🏆'
        
        group_title = "Group"
        group_username = None
        try:
            chat = await bot.get_chat(group_id)
            group_title = chat.title or "Group"
            group_username = chat.username
        except Exception as chat_err:
            logger.error(f"Error fetching chat info for group {group_id}: {chat_err}")
            
        msg_id = battle.get("message_id")
        link = ""
        if msg_id:
            if group_username:
                link = f"https://t.me/{group_username}/{msg_id}"
            elif str(group_id).startswith("-100"):
                link = f"https://t.me/c/{str(group_id)[4:]}/{msg_id}"
                
        if link:
            group_info = f"<a href='{link}'>{group_title}</a>"
        elif group_username:
            group_info = f"{group_title} (@{group_username})"
        else:
            group_info = f"{group_title} ({group_id})"
            
        from src.utils.logging_helper import send_log
        log_text = (
            f"{emoji} {html.bold(title)} {emoji}\n\n"
            f"• {html.bold('Battle ID:')} {html.code(battle_id)}\n"
            f"• {html.bold('Group:')} {group_info}\n"
            f"• {html.bold('Problem:')} {battle['problem_title']}\n"
            f"• {html.bold('Total Players:')} {len(participants)}\n"
            f"• {html.bold('Winner:')} {final_ranking[0]['first_name'] or final_ranking[0]['username'] if final_ranking and final_ranking[0]['solved_at'] is not None else 'None'}"
        )
        await send_log(log_text, disable_notification=True)
    except Exception as log_err:
        logger.error(f"Error logging group battle end/expiration: {log_err}")





async def check_srs_reviews():
    """
    Daily check for pending reviews and notify users.
    """
    logger.info("Checking due SRS reviews...")
    try:
        # Get today's local date for cache key
        today_local_date = datetime.date.today()
        # Fetch all users
        rows = await db.fetch("SELECT telegram_id FROM users")
        for r in rows:
            user_id = r["telegram_id"]

            # Prevent duplicate notifications/reminders on the same calendar day
            sent_cache_key = f"srs_reminder:sent:{today_local_date}:{user_id}"
            already_sent = await cache_manager.get(sent_cache_key)
            if already_sent:
                logger.info(f"SRS reminder check: User {user_id} has ALREADY been sent a reminder today. Skipping.")
                continue

            due_reviews = await db.get_due_srs_reviews(user_id)
            if due_reviews:
                count = len(due_reviews)
                logger.info(f"SRS reminder check: User {user_id} has {count} due reviews. SENDING alert now...")
                reminder_msg = (
                    f"🧠 {html.bold('Spaced Repetition Review Due!')}\n\n"
                    f"You have {html.bold(count)} LeetCode problems due for review today to reinforce memory retention.\n"
                    f"Solve them and use `/solved` to log your review quality and update schedules!\n\n"
                    f"Let's maintain your learning streak! 💪"
                )
                reminder_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="📋 View Reviews Queue", callback_data="cmd_reviews")
                ]])
                try:
                    await bot.send_message(
                        chat_id=user_id, text=reminder_msg, parse_mode="HTML",
                        reply_markup=reminder_keyboard
                    )
                    await cache_manager.set(sent_cache_key, "1", expire_seconds=86400)
                    await asyncio.sleep(0.05)
                except Exception as e:
                    logger.error(f"Failed to send SRS reminder to {user_id}: {e}")
            else:
                logger.info(f"SRS reminder check: User {user_id} has NO due reviews today. Skipping.")
    except Exception as e:
        logger.error(f"Error checking SRS reviews: {e}", exc_info=True)
        tb = traceback.format_exc()
        if len(tb) > 2500:
            tb = tb[:2500] + "\n...[truncated]"
        error_msg = (
            f"🚨 {html.bold('CRITICAL: Error in Background Task (check_srs_reviews)')} 🚨\n\n"
            f"⚠️ {html.bold('Error:')} {html.code(str(e))}\n\n"
            f"📂 {html.bold('Traceback:')}\n<pre><code class='language-python'>{html_escape(tb)}</code></pre>"
        )
        from src.utils.logging_helper import send_log

        await send_log(error_msg, pin=True, disable_notification=False)


async def check_user_streak_reminder(
    user_id: int, leetcode_username: Optional[str]
) -> bool:
    """
    Check and send streak warning/auto-log for a single user.
    Returns True if a message was sent or problem was auto-logged, False otherwise.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    today_utc_date = now_utc.date()

    sent_cache_key = f"streak_reminder:sent:{today_utc_date}:{user_id}"
    already_sent = await cache_manager.get(sent_cache_key)
    if already_sent:
        logger.info(f"Streak reminder check: User {user_id} has ALREADY been sent an alert today. Skipping.")
        return False

    solved_today = False
    solved_sub = None

    if leetcode_username:
        try:
            submissions = await leetcode_client.get_recent_accepted_submissions(
                leetcode_username, limit=5
            )
            for sub in submissions:
                sub_time = datetime.datetime.fromtimestamp(
                    int(sub["timestamp"]), tz=datetime.timezone.utc
                )
                if sub_time.date() == today_utc_date:
                    solved_today = True
                    solved_sub = sub
                    break
        except Exception as api_err:
            logger.error(
                f"Error checking recent submissions for {leetcode_username}: {api_err}"
            )

    if solved_today and solved_sub:
        try:
            problem_slug = solved_sub["titleSlug"]
            problem_title = solved_sub["title"]
            # Fetch problem details to get difficulty
            problem = await leetcode_client.get_problem_details(problem_slug)
            difficulty = problem["difficulty"] if problem else "Medium"

            # Auto-log solved problem
            await db.record_solved_problem(
                user_id, problem_slug, problem_title, difficulty
            )
            await db.add_xp_coins(user_id, xp=15, coins=5)

            success_msg = (
                f"🎉 {html.bold('Daily Solve Auto-Detected!')} 🏆\n\n"
                f"We noticed you solved {html.bold(html_escape(problem_title))} on LeetCode today!\n"
                f"Since you hadn't logged it yet, we went ahead and auto-logged it to keep your daily streak alive. 🔥\n\n"
                f"🎁 Awarded {html.bold('15 XP')} and {html.bold('5 coins')}!\n\n"
                f"💡 {html.italic('Note: If you ever want this problem scheduled for spaced repetition reviews, please run:')}\n"
                f"`/solved {problem_slug} &lt;quality&gt;`"
            )
            logger.info(f"Streak reminder check: User {user_id} solved today ({problem_title}). SENDING auto-detect alert...")
            await bot.send_message(chat_id=user_id, text=success_msg, parse_mode="HTML")
            await cache_manager.set(sent_cache_key, "1", expire_seconds=86400)
            return True
        except Exception as inner_err:
            logger.error(
                f"Failed to auto-log solve or notify user {user_id}: {inner_err}"
            )
    else:
        # Send the warning
        warning_msg = (
            f"🔥 {html.bold('Daily Solve Streak Warning!')} 🚨\n\n"
            f"You haven't logged any solved problem today!\n"
            f"Solve a problem on LeetCode and log it using `/solved &lt;problem_slug&gt; &lt;quality&gt;` to maintain your daily streak and earn XP/coins! 📈\n\n"
            f"Don't break the chain! 💪"
        )
        try:
            logger.info(f"Streak reminder check: User {user_id} has NOT solved today. SENDING streak warning alert...")
            await bot.send_message(chat_id=user_id, text=warning_msg, parse_mode="HTML")
            await cache_manager.set(sent_cache_key, "1", expire_seconds=86400)
            return True
        except Exception as inner_err:
            logger.error(
                f"Failed to send streak warning to user {user_id}: {inner_err}"
            )
    return False


async def check_streak_reminders():
    """
    Daily check at 15:00 UTC to warn users who haven't solved any problems today,
    automatically checking their verified LeetCode profile first if linked.
    """
    logger.info("Checking solve streak reminders...")
    try:
        users_to_check = await db.get_users_for_streak_check()
        for u in users_to_check:
            await check_user_streak_reminder(u["telegram_id"], u["leetcode_username"])
            await asyncio.sleep(0.05)
    except Exception as e:
        logger.error(f"Error checking streak reminders: {e}", exc_info=True)
        tb = traceback.format_exc()
        if len(tb) > 2500:
            tb = tb[:2500] + "\n...[truncated]"
        error_msg = (
            f"🚨 {html.bold('CRITICAL: Error in Background Task (check_streak_reminders)')} 🚨\n\n"
            f"⚠️ {html.bold('Error:')} {html.code(str(e))}\n\n"
            f"📂 {html.bold('Traceback:')}\n<pre><code class='language-python'>{html_escape(tb)}</code></pre>"
        )
        from src.utils.logging_helper import send_log

        await send_log(error_msg, pin=True, disable_notification=False)


async def trigger_streak_reminder_for_user(user_id: int):
    """
    Checks and triggers streak reminder warning/auto-log for a specific user.
    Used when a user enables the streak warning setting after the daily schedule time.
    """
    # Check if it is past 15:00 UTC today
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    scheduled_time = now_utc.replace(hour=15, minute=0, second=0, microsecond=0)

    if now_utc < scheduled_time:
        return

    try:
        # Get linked account details
        link = await db.get_linked_account(user_id)
        leetcode_username = (
            link["leetcode_username"] if (link and link["verified"]) else None
        )

        # Check if user already has a solve logged in DB today
        has_solve_logged = await db.fetchrow(
            "SELECT 1 FROM problem_history WHERE telegram_id = $1 AND solved_at::date = CURRENT_DATE",
            user_id,
        )
        if has_solve_logged:
            return

        await check_user_streak_reminder(user_id, leetcode_username)
    except Exception as e:
        logger.error(f"Error in trigger_streak_reminder_for_user: {e}")


async def check_missed_jobs():
    """
    Checks if daily cron jobs were missed while the bot was offline and runs them if necessary.
    """
    await asyncio.sleep(10)  # Wait for startup connections to settle
    logger.info("Running check for missed daily jobs...")

    # 1. Check SRS Reviews (scheduled daily at 9:00 AM local system time)
    local_now = datetime.datetime.now()
    if local_now.hour >= 9:
        logger.info(
            "Bot started after 9:00 AM local time. Running check_srs_reviews for any missed reminders today..."
        )
        try:
            await check_srs_reviews()
        except Exception as e:
            logger.error(f"Error running missed SRS reviews check: {e}")

    # 2. Check Streak Reminders (scheduled daily at 15:00 UTC / 8:30 PM IST)
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    if utc_now.hour >= 15:
        logger.info(
            "Bot started after 15:00 UTC. Running check_streak_reminders for any missed warnings today..."
        )
        try:
            await check_streak_reminders()
        except Exception as e:
            logger.error(f"Error running missed streak reminders check: {e}")


async def poll_leetcode_feed():
    """
    Background job to poll LeetCode for daily challenge updates and contest alerts.
    Runs every 5 minutes.
    """
    logger.info("Polling LeetCode feed updates...")
    try:
        channels = list(settings.leetcode_feed_channels)
        try:
            active_groups = await db.fetch(
                "SELECT group_id FROM group_settings WHERE setting_name = 'feed' AND setting_value = 'enable'"
            )
            for row in active_groups:
                channels.append(row["group_id"])
        except Exception as db_err:
            logger.error(f"Error loading group feed subscribers: {db_err}")

        if not channels:
            return

        now = datetime.datetime.now(datetime.timezone.utc)
        now_ts = now.timestamp()

        # 1. Process Daily Challenge
        daily = await leetcode_client.get_daily_challenge()
        if daily:
            daily_date = daily["date"]  # Format: "YYYY-MM-DD"
            try:
                await db.record_daily_challenge(
                    daily_date, daily["question"]["titleSlug"]
                )
            except Exception as e:
                logger.error(f"Error recording daily challenge in DB: {e}")
            cache_key = f"leetcode_feed:daily_posted:{daily_date}"
            already_posted = await cache_manager.get(cache_key)
            if not already_posted:
                question = daily["question"]
                title = question["title"]
                difficulty = question["difficulty"]
                tags = [t["name"] for t in question["topicTags"]]
                link = f"https://leetcode.com{daily['link']}"
                diff_emoji = (
                    "🟢"
                    if difficulty == "Easy"
                    else "🟡" if difficulty == "Medium" else "🔴"
                )

                clean_description = clean_leetcode_html(
                    question["content"], max_length=1500
                )

                daily_summary_msg = (
                    f"📅 {html.bold('LeetCode Daily Coding Challenge')} ({daily_date})\n\n"
                    f"🏆 {html.bold(html_escape(title))}\n"
                    f"Difficulty: {diff_emoji} {html.bold(html_escape(difficulty))}\n"
                    f"Tags: {html.italic(', '.join([html_escape(t) for t in tags]))}\n"
                    f"🔗 Link: <a href='{link}'>Solve on LeetCode</a>\n\n"
                    f"💡 {html.italic('Click the button below to view the full description inside the bot!')}"
                )

                # Fetch bot info to get username dynamically
                try:
                    bot_user = await bot.get_me()
                    bot_username = bot_user.username
                except Exception as info_err:
                    logger.error(f"Error fetching bot username: {info_err}")
                    bot_username = "MemoizeLC_bot"

                feed_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="👁️ View Full Question",
                                url=f"https://t.me/{bot_username}?start=daily",
                            )
                        ]
                    ]
                )

                dm_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="👁️ View Description",
                                callback_data="view_daily_desc",
                            )
                        ]
                    ]
                )

                for cid in channels:
                    try:
                        await bot.send_message(
                            chat_id=cid,
                            text=daily_summary_msg,
                            parse_mode="HTML",
                            reply_markup=feed_keyboard,
                            disable_web_page_preview=True,
                        )
                    except Exception as e:
                        logger.error(
                            f"Error sending daily challenge to feed channel {cid}: {e}"
                        )

                # Send to users who enabled daily challenge reminders
                try:
                    daily_users = await db.get_users_with_daily_reminders()
                    for uid in daily_users:
                        try:
                            await bot.send_message(
                                chat_id=uid,
                                text=daily_summary_msg,
                                parse_mode="HTML",
                                reply_markup=dm_keyboard,
                                disable_web_page_preview=True,
                            )
                            await asyncio.sleep(0.05)
                        except Exception as user_err:
                            logger.error(
                                f"Failed to send daily challenge reminder to user {uid}: {user_err}"
                            )
                except Exception as db_err:
                    logger.error(f"Failed to fetch daily challenge users: {db_err}")

                await cache_manager.set(cache_key, "1", expire_seconds=172800)

        # 2. Process Contests
        contests = await leetcode_client.get_contests()
        for c in contests:
            slug = c["titleSlug"]
            title = c["title"]
            start_time = int(c["startTime"])
            duration = int(c["duration"])
            end_time = start_time + duration

            start_dt = datetime.datetime.fromtimestamp(
                start_time, tz=datetime.timezone.utc
            )
            duration_mins = duration // 60

            # Registration alert (Contest is upcoming and we haven't alerted yet)
            if start_time > now_ts:
                reg_cache_key = f"leetcode_feed:contest_alert_reg:{slug}"
                reg_posted = await cache_manager.get(reg_cache_key)
                if not reg_posted:
                    reg_msg = (
                        f"📢 {html.bold('New LeetCode Contest Available!')} 🏆\n\n"
                        f"🎯 {html.bold(html_escape(title))}\n"
                        f"⏰ {html.bold('Starts:')} {start_dt.strftime('%d %b %Y, %I:%M %p UTC')}\n"
                        f"⏱️ {html.bold('Duration:')} {duration_mins} minutes\n\n"
                        f"🔗 <a href='https://leetcode.com/contest/{slug}'>Register here on LeetCode</a>"
                    )
                    for cid in channels:
                        try:
                            await bot.send_message(
                                chat_id=cid, text=reg_msg, parse_mode="HTML"
                            )
                        except Exception as e:
                            logger.error(
                                f"Error sending contest reg alert to feed {cid}: {e}"
                            )
                    await cache_manager.set(reg_cache_key, "1", expire_seconds=604800)

                # Today alert (starts in <= 12 hours)
                time_to_start = start_time - now_ts
                if time_to_start <= 43200:
                    today_cache_key = f"leetcode_feed:contest_alert_today:{slug}"
                    today_posted = await cache_manager.get(today_cache_key)
                    if not today_posted:
                        hours_left = int(time_to_start // 3600)
                        mins_left = int((time_to_start % 3600) // 60)
                        countdown_str = (
                            f"{hours_left}h {mins_left}m"
                            if hours_left > 0
                            else f"{mins_left}m"
                        )

                        today_msg = (
                            f"⚠️ {html.bold('LeetCode Contest Today!')} 🚨\n\n"
                            f"🏆 {html.bold(html_escape(title))}\n"
                            f"⏳ {html.bold('Starting in:')} {html.code(countdown_str)}\n"
                            f"⏰ {html.bold('Start Time:')} {start_dt.strftime('%I:%M %p UTC')}\n"
                            f"⏱️ {html.bold('Duration:')} {duration_mins} minutes\n\n"
                            f"🔗 <a href='https://leetcode.com/contest/{slug}'>Make sure you are registered!</a>"
                        )
                        for cid in channels:
                            try:
                                await bot.send_message(
                                    chat_id=cid, text=today_msg, parse_mode="HTML"
                                )
                            except Exception as e:
                                logger.error(
                                    f"Error sending contest today alert to feed {cid}: {e}"
                                )

                        # Send to users who enabled contest reminders
                        try:
                            contest_users = await db.get_users_with_contest_reminders()
                            for uid in contest_users:
                                try:
                                    await bot.send_message(
                                        chat_id=uid, text=today_msg, parse_mode="HTML"
                                    )
                                    await asyncio.sleep(0.05)
                                except Exception as user_err:
                                    logger.error(
                                        f"Failed to send contest today warning to user {uid}: {user_err}"
                                    )
                        except Exception as db_err:
                            logger.error(
                                f"Failed to fetch contest reminder users: {db_err}"
                            )

                        await cache_manager.set(
                            today_cache_key, "1", expire_seconds=86400
                        )

                # Starting alert (starts in <= 5 minutes)
                if time_to_start <= 300:
                    start_cache_key = f"leetcode_feed:contest_alert_start:{slug}"
                    start_posted = await cache_manager.get(start_cache_key)
                    if not start_posted:
                        start_msg = (
                            f"🚀 {html.bold('LeetCode Contest Starting Now!')} ⚔️\n\n"
                            f"🏆 {html.bold(html_escape(title))} is beginning!\n"
                            f"⏱️ {html.bold('Duration:')} {duration_mins} minutes\n\n"
                            f"🔗 <a href='https://leetcode.com/contest/{slug}'>Enter Contest Arena</a>\n\n"
                            f"Good luck and high rating boosts to all participants! 💪"
                        )
                        for cid in channels:
                            try:
                                await bot.send_message(
                                    chat_id=cid, text=start_msg, parse_mode="HTML"
                                )
                            except Exception as e:
                                logger.error(
                                    f"Error sending contest start alert to feed {cid}: {e}"
                                )

                        # Send to users who enabled contest reminders
                        try:
                            contest_users = await db.get_users_with_contest_reminders()
                            for uid in contest_users:
                                try:
                                    await bot.send_message(
                                        chat_id=uid, text=start_msg, parse_mode="HTML"
                                    )
                                    await asyncio.sleep(0.05)
                                except Exception as user_err:
                                    logger.error(
                                        f"Failed to send contest starting warning to user {uid}: {user_err}"
                                    )
                        except Exception as db_err:
                            logger.error(
                                f"Failed to fetch contest reminder users: {db_err}"
                            )

                        await cache_manager.set(
                            start_cache_key, "1", expire_seconds=7200
                        )

            # Ending alert (ended in the last 10 minutes)
            time_since_end = now_ts - end_time
            if 0 <= time_since_end <= 600:
                end_cache_key = f"leetcode_feed:contest_alert_end:{slug}"
                end_posted = await cache_manager.get(end_cache_key)
                if not end_posted:
                    end_msg = (
                        f"🏁 {html.bold('LeetCode Contest has Ended!')} 🏆\n\n"
                        f"🏆 {html.bold(html_escape(title))} has finished.\n\n"
                        f"How did it go? Discuss solutions, analyze your complexity using `/analyze`, or review code structures using `/review` with @MemoizeLC_bot! 🧠"
                    )
                    for cid in channels:
                        try:
                            await bot.send_message(
                                chat_id=cid, text=end_msg, parse_mode="HTML"
                            )
                        except Exception as e:
                            logger.error(
                                f"Error sending contest end alert to feed {cid}: {e}"
                            )
                    await cache_manager.set(end_cache_key, "1", expire_seconds=7200)

    except Exception as e:
        logger.error(f"Error in poll_leetcode_feed: {e}", exc_info=True)
        tb = traceback.format_exc()
        if len(tb) > 2500:
            tb = tb[:2500] + "\n...[truncated]"
        error_msg = (
            f"🚨 {html.bold('CRITICAL: Error in Background Task (poll_leetcode_feed)')} 🚨\n\n"
            f"⚠️ {html.bold('Error:')} {html.code(str(e))}\n\n"
            f"📂 {html.bold('Traceback:')}\n<pre><code class='language-python'>{html_escape(tb)}</code></pre>"
        )
        from src.utils.logging_helper import send_log

        await send_log(error_msg, pin=True, disable_notification=False)


@dp.errors()
async def global_error_handler(event: ErrorEvent):
    exception = event.exception
    update = event.update

    # Silently ignore "message is not modified" — harmless double-taps on inline
    # buttons where the content is identical to what's already rendered.
    if isinstance(exception, TelegramBadRequest) and "message is not modified" in str(exception):
        logger.debug(f"Suppressed harmless 'message not modified' error from update {event.update.update_id}")
        return

    logger.error(f"Unhandled exception in bot: {exception}", exc_info=exception)

    from src.utils.logging_helper import send_error_log
    await send_error_log(exception, context_label="Unhandled Exception in Bot", update=update)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect database pool
    await db.connect()

    # Register Bot routes
    dp.include_router(get_main_router())

    allowed_updates = dp.resolve_used_update_types()

    # Webhook mode vs Polling mode setup
    if settings.WEBHOOK_URL:
        # Register webhook URL
        webhook_full_url = f"{settings.WEBHOOK_URL.rstrip('/')}{settings.WEBHOOK_PATH}"
        logger.info(f"Setting webhook to: {webhook_full_url} with allowed_updates={allowed_updates}")
        await bot.set_webhook(url=webhook_full_url, allowed_updates=allowed_updates, drop_pending_updates=True)
    else:
        logger.info(
            f"No WEBHOOK_URL found. Bot will run in polling mode asynchronously with allowed_updates={allowed_updates}"
        )
        await bot.delete_webhook(drop_pending_updates=True)
        # Run dispatcher polling in the background event loop
        asyncio.create_task(dp.start_polling(bot, allowed_updates=allowed_updates))

    # Setup scheduler jobs
    # Poll all active battles (1v1 and group) every 30 seconds
    scheduler.add_job(
        poll_all_active_battles,
        "interval",
        seconds=30,
        misfire_grace_time=60,
        id="poll_all_active_battles",
        replace_existing=True,
    )
    # Check SRS reviews once a day (at 9 AM)
    scheduler.add_job(
        check_srs_reviews,
        "cron",
        hour=9,
        minute=0,
        misfire_grace_time=3600,
        id="srs_reviews",
        replace_existing=True,
    )
    # Check daily solve streak at 15:00 UTC (8:30 PM IST)
    scheduler.add_job(
        check_streak_reminders,
        "cron",
        hour=15,
        minute=0,
        timezone="UTC",
        misfire_grace_time=3600,
        id="streak_reminders",
        replace_existing=True,
    )
    # Poll LeetCode challenge and contests every 5 minutes
    scheduler.add_job(
        poll_leetcode_feed,
        "interval",
        minutes=5,
        misfire_grace_time=60,
        id="poll_leetcode_feed",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started.")

    # Run LeetCode feed poll immediately on startup in a background task
    asyncio.create_task(poll_leetcode_feed())

    # Run missed daily jobs check in a background task
    asyncio.create_task(check_missed_jobs())

    # Send bot startup notification to log channel
    from src.utils.logging_helper import send_log

    startup_msg = (
        f"🤖 {html.bold('Memoize Bot is UP and Running')} 🚀\n\n"
        f"⏰ {html.bold('Started at:')} {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        f"⚙️ {html.bold('Mode:')} {html.code('Webhook' if settings.WEBHOOK_URL else 'Polling')}"
    )
    await send_log(startup_msg, disable_notification=True)

    # Send public online notification to all configured public & LeetCode feed channels
    target_channels = set(settings.public_channels + settings.leetcode_feed_channels)
    if target_channels:
        public_msg = (
            f"⚡ {html.bold('Memoize Companion Bot is Online!')} 🚀\n\n"
            f"The bot is active and ready to handle your LeetCode daily challenges, spaced repetition reviews, speed battles, and AI queries!\n\n"
            f"👉 Click here to start practicing: @MemoizeLC_bot\n\n"
            f"🎯 Join us to maintain your discipline and level up your coding skills!"
        )
        for channel_id in target_channels:
            try:
                await bot.send_message(
                    chat_id=channel_id, text=public_msg, parse_mode="HTML"
                )
            except Exception as e:
                logger.error(
                    f"Failed to send startup message to channel {channel_id}: {e}",
                    exc_info=True,
                )

    yield

    # Shutdown logic
    scheduler.shutdown()
    logger.info("Scheduler shutdown.")
    await bot.session.close()
    await leetcode_client.close()
    await cache_manager.close()
    await db.close()


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def log_request_latency(request: Request, call_next):
    import time
    start_time = time.time()
    response = await call_next(request)
    latency = (time.time() - start_time) * 1000
    if latency > 5000:
        logger.warning(f"SLOW HTTP Request ({latency:.1f}ms): {request.method} {request.url.path}")
    return response


@app.post(settings.WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    """
    Receives webhooks from Telegram and pushes to aiogram.
    """
    try:
        update_json = await request.json()
        update = types.Update.model_validate(update_json, context={"bot": bot})
        await dp.feed_update(bot, update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook update processing error: {e}", exc_info=True)
        tb = traceback.format_exc()
        if len(tb) > 2500:
            tb = tb[:2500] + "\n...[truncated]"
        error_msg = (
            f"🚨 {html.bold('CRITICAL: Error in Webhook Ingestion')} 🚨\n\n"
            f"⚠️ {html.bold('Error:')} {html.code(str(e))}\n\n"
            f"📂 {html.bold('Traceback:')}\n<pre><code class='language-python'>{html_escape(tb)}</code></pre>"
        )
        from src.utils.logging_helper import send_log

        await send_log(error_msg, pin=True, disable_notification=False)
        return {"status": "error", "message": str(e)}


@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    """
    Health check endpoint pinged by UptimeRobot.
    """
    return {
        "status": "healthy",
        "time": datetime.datetime.now().isoformat(),
        "database": "connected" if db.pool else "disconnected",
    }


if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=settings.PORT, reload=False)
