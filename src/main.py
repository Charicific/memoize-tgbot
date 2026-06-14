import asyncio
import logging
import datetime
import traceback
from html import escape as html_escape
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, html, types, BaseMiddleware

from aiogram.types import ErrorEvent
from aiogram.fsm.storage.redis import RedisStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from src.config import settings
from src.services.supabase_db import db
from src.services.redis_cache import cache_manager
from src.services.leetcode import LeetCodeClient
from src.handlers import get_main_router
from src.utils.formatters import clean_leetcode_html



# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Initialize clients
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher(storage=cache_manager.fsm_storage)
leetcode_client = LeetCodeClient()

class GroupMemberMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, types.Message) and event.chat.type in ["group", "supergroup"]:
            if event.from_user:
                try:
                    await db.record_group_member(
                        group_id=event.chat.id,
                        telegram_id=event.from_user.id,
                        username=event.from_user.username,
                        first_name=event.from_user.first_name
                    )
                except Exception as e:
                    logger.error(f"Error in GroupMemberMiddleware: {e}")
        return await handler(event, data)

dp.message.outer_middleware(GroupMemberMiddleware())


# Initialize Scheduler
# SQLAlchemyJobStore persists jobs into Postgres so they survive restarts
jobstores = {
    'default': SQLAlchemyJobStore(url=settings.SUPABASE_DB_URL.replace("postgresql+asyncpg://", "postgresql://"))
}
scheduler = AsyncIOScheduler(jobstores=jobstores)


async def poll_active_battles():
    """
    Background scheduler job to poll active battles every minute.
    """
    logger.info("Polling active battles...")
    try:
        active_battles = await db.get_active_battles()
        for battle in active_battles:
            now = datetime.datetime.now(datetime.timezone.utc)
            expires_at = battle["expires_at"]
            
            if isinstance(expires_at, str):
                expires_at = datetime.datetime.fromisoformat(expires_at.replace("Z", "+00:00"))

            # Handle expiry
            if now > expires_at:
                await db.update_battle_status(battle["id"], "EXPIRED")
                expired_msg = f"⏱️ Battle for {html.bold(battle['problem_title'])} has expired because time limit was reached."
                try:
                    await bot.send_message(chat_id=battle["challenger_id"], text=expired_msg, parse_mode="HTML")
                    await bot.send_message(chat_id=battle["opponent_id"], text=expired_msg, parse_mode="HTML")
                except Exception as e:
                    logger.error(f"Error sending battle expiration notification: {e}")
                continue

            if battle["status"] != "ACTIVE":
                continue

            started_at = battle["started_at"]
            if isinstance(started_at, str):
                started_at = datetime.datetime.fromisoformat(started_at.replace("Z", "+00:00"))

            # Fetch account details
            challenger_link = await db.get_linked_account(battle["challenger_id"])
            opponent_link = await db.get_linked_account(battle["opponent_id"])

            if not challenger_link or not opponent_link:
                continue

            c_user = challenger_link["leetcode_username"]
            o_user = opponent_link["leetcode_username"]

            # Fetch recent accepted submissions
            c_subs = await leetcode_client.get_recent_accepted_submissions(c_user, limit=5)
            o_subs = await leetcode_client.get_recent_accepted_submissions(o_user, limit=5)

            c_solved_ts = None
            o_solved_ts = None

            for sub in c_subs:
                if sub["titleSlug"] == battle["problem_slug"]:
                    sub_time = datetime.datetime.fromtimestamp(int(sub["timestamp"]), tz=datetime.timezone.utc)
                    if sub_time > started_at:
                        c_solved_ts = sub_time
                        break

            for sub in o_subs:
                if sub["titleSlug"] == battle["problem_slug"]:
                    sub_time = datetime.datetime.fromtimestamp(int(sub["timestamp"]), tz=datetime.timezone.utc)
                    if sub_time > started_at:
                        o_solved_ts = sub_time
                        break

            winner_id = None
            loser_id = None

            if c_solved_ts and o_solved_ts:
                # Both solved, check who solved first
                if c_solved_ts < o_solved_ts:
                    winner_id = battle["challenger_id"]
                    loser_id = battle["opponent_id"]
                else:
                    winner_id = battle["opponent_id"]
                    loser_id = battle["challenger_id"]
            elif c_solved_ts:
                winner_id = battle["challenger_id"]
                loser_id = battle["opponent_id"]
            elif o_solved_ts:
                winner_id = battle["opponent_id"]
                loser_id = battle["challenger_id"]

            if winner_id:
                await db.update_battle_status(battle["id"], "COMPLETED", winner_id=winner_id, ended_at=now)
                # Award points
                await db.add_xp_coins(winner_id, xp=100, coins=20)
                await db.add_xp_coins(loser_id, xp=20, coins=0)

                # Get usernames
                winner_row = await db.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", winner_id)
                loser_row = await db.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", loser_id)

                w_name = winner_row["first_name"] or winner_row["username"] or "Winner"
                l_name = loser_row["first_name"] or loser_row["username"] or "Loser"

                winner_url = f"https://leetcode.com/problems/{battle['problem_slug']}"
                result_msg = (
                    f"🎉 {html.bold('LeetCode Battle Completed!')} 🎉\n\n"
                    f"🏆 Problem: <a href='{winner_url}'>{battle['problem_title']}</a>\n"
                    f"🥇 Winner: {html.bold(w_name)} (Awarded 100 XP, 20 coins)\n"
                    f"🥈 Loser: {html.bold(l_name)} (Awarded 20 XP)\n\n"
                    f"Congratulations to both players for competing!"
                )

                try:
                    await bot.send_message(chat_id=battle["challenger_id"], text=result_msg, parse_mode="HTML", disable_web_page_preview=True)
                    await bot.send_message(chat_id=battle["opponent_id"], text=result_msg, parse_mode="HTML", disable_web_page_preview=True)
                except Exception as e:
                    logger.error(f"Error sending battle completed message: {e}")
    except Exception as e:
        logger.error(f"Error in poll_active_battles: {e}", exc_info=True)
        tb = traceback.format_exc()
        if len(tb) > 2500:
            tb = tb[:2500] + "\n...[truncated]"
        error_msg = (
            f"🚨 {html.bold('CRITICAL: Error in Background Task (poll_active_battles)')} 🚨\n\n"
            f"⚠️ {html.bold('Error:')} {html.code(str(e))}\n\n"
            f"📂 {html.bold('Traceback:')}\n<pre><code class='language-python'>{html_escape(tb)}</code></pre>"
        )
        from src.utils.logging_helper import send_log
        await send_log(error_msg, pin=True, disable_notification=False)


async def check_srs_reviews():
    """
    Daily check for pending reviews and notify users.
    """
    logger.info("Checking due SRS reviews...")
    try:
        # Fetch all users
        rows = await db.fetch("SELECT telegram_id FROM users")
        for r in rows:
            user_id = r["telegram_id"]
            due_reviews = await db.get_due_srs_reviews(user_id)
            if due_reviews:
                count = len(due_reviews)
                reminder_msg = (
                    f"🧠 {html.bold('Spaced Repetition Review Due!')}\n\n"
                    f"You have {html.bold(count)} LeetCode problems due for review today to reinforce memory retention.\n"
                    f"Solve them and use `/solved` to log your review quality and update schedules!\n\n"
                    f"Let's maintain your learning streak! 💪"
                )
                try:
                    await bot.send_message(chat_id=user_id, text=reminder_msg, parse_mode="HTML")
                except Exception as e:
                    logger.error(f"Failed to send SRS reminder to {user_id}: {e}")
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


async def poll_leetcode_feed():
    """
    Background job to poll LeetCode for daily challenge updates and contest alerts.
    Runs every 5 minutes.
    """
    logger.info("Polling LeetCode feed updates...")
    try:
        channels = settings.leetcode_feed_channels
        if not channels:
            return

        now = datetime.datetime.now(datetime.timezone.utc)
        now_ts = now.timestamp()

        # 1. Process Daily Challenge
        daily = await leetcode_client.get_daily_challenge()
        if daily:
            daily_date = daily["date"]  # Format: "YYYY-MM-DD"
            cache_key = f"leetcode_feed:daily_posted:{daily_date}"
            already_posted = await cache_manager.get(cache_key)
            if not already_posted:
                question = daily["question"]
                title = question["title"]
                difficulty = question["difficulty"]
                tags = [t["name"] for t in question["topicTags"]]
                link = f"https://leetcode.com{daily['link']}"
                diff_emoji = "🟢" if difficulty == "Easy" else "🟡" if difficulty == "Medium" else "🔴"
                
                clean_description = clean_leetcode_html(question["content"], max_length=1500)
                
                daily_msg = (
                    f"📅 {html.bold('LeetCode Daily Coding Challenge')} ({daily_date})\n\n"
                    f"🏆 {html.bold(html_escape(title))}\n"
                    f"Difficulty: {diff_emoji} {html.bold(html_escape(difficulty))}\n"
                    f"Tags: {html.italic(', '.join([html_escape(t) for t in tags]))}\n"
                    f"🔗 Link: <a href='{link}'>Solve on LeetCode</a>\n\n"
                    f"{html.bold('Description:')}\n"
                    f"{clean_description}\n\n"
                    f"💡 {html.italic('To get progressive hints for this problem, type:')}\n"
                    f"`/hint {question['titleSlug']}` in @MemoizeLC_bot"
                )
                
                for cid in channels:
                    try:
                        await bot.send_message(chat_id=cid, text=daily_msg, parse_mode="HTML", disable_web_page_preview=True)
                    except Exception as e:
                        logger.error(f"Error sending daily challenge to feed channel {cid}: {e}")
                
                await cache_manager.set(cache_key, "1", expire_seconds=172800)

        # 2. Process Contests
        contests = await leetcode_client.get_contests()
        for c in contests:
            slug = c["titleSlug"]
            title = c["title"]
            start_time = int(c["startTime"])
            duration = int(c["duration"])
            end_time = start_time + duration
            
            start_dt = datetime.datetime.fromtimestamp(start_time, tz=datetime.timezone.utc)
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
                            await bot.send_message(chat_id=cid, text=reg_msg, parse_mode="HTML")
                        except Exception as e:
                            logger.error(f"Error sending contest reg alert to feed {cid}: {e}")
                    await cache_manager.set(reg_cache_key, "1", expire_seconds=604800)

                # Today alert (starts in <= 12 hours)
                time_to_start = start_time - now_ts
                if time_to_start <= 43200:
                    today_cache_key = f"leetcode_feed:contest_alert_today:{slug}"
                    today_posted = await cache_manager.get(today_cache_key)
                    if not today_posted:
                        hours_left = int(time_to_start // 3600)
                        mins_left = int((time_to_start % 3600) // 60)
                        countdown_str = f"{hours_left}h {mins_left}m" if hours_left > 0 else f"{mins_left}m"
                        
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
                                await bot.send_message(chat_id=cid, text=today_msg, parse_mode="HTML")
                            except Exception as e:
                                logger.error(f"Error sending contest today alert to feed {cid}: {e}")
                        await cache_manager.set(today_cache_key, "1", expire_seconds=86400)

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
                                await bot.send_message(chat_id=cid, text=start_msg, parse_mode="HTML")
                            except Exception as e:
                                logger.error(f"Error sending contest start alert to feed {cid}: {e}")
                        await cache_manager.set(start_cache_key, "1", expire_seconds=7200)

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
                            await bot.send_message(chat_id=cid, text=end_msg, parse_mode="HTML")
                        except Exception as e:
                            logger.error(f"Error sending contest end alert to feed {cid}: {e}")
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
    logger.error(f"Unhandled exception in bot: {exception}", exc_info=exception)
    
    # Extract update context
    update_str = "Unknown Update"
    try:
        update_str = update.model_dump_json(indent=2)
    except Exception:
        update_str = str(update)
        
    tb = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
    if len(tb) > 2500:
        tb = tb[:2500] + "\n...[truncated]"

    error_msg = (
        f"🚨 {html.bold('CRITICAL: Unhandled Exception in Bot')} 🚨\n\n"
        f"⚠️ {html.bold('Error:')} {html.code(str(exception))}\n\n"
        f"📂 {html.bold('Traceback:')}\n<pre><code class='language-python'>{html_escape(tb)}</code></pre>\n\n"
        f"📥 {html.bold('Triggering Update:')}\n<pre><code class='language-json'>{html_escape(update_str[:1000])}</code></pre>"
    )
    
    from src.utils.logging_helper import send_log
    await send_log(error_msg, pin=True, disable_notification=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect database pool
    await db.connect()

    # Register Bot routes
    dp.include_router(get_main_router())

    # Webhook mode vs Polling mode setup
    if settings.WEBHOOK_URL:
        # Register webhook URL
        webhook_full_url = f"{settings.WEBHOOK_URL.rstrip('/')}{settings.WEBHOOK_PATH}"
        logger.info(f"Setting webhook to: {webhook_full_url}")
        await bot.set_webhook(url=webhook_full_url, drop_pending_updates=True)
    else:
        logger.info("No WEBHOOK_URL found. Bot will run in polling mode asynchronously.")
        await bot.delete_webhook(drop_pending_updates=True)
        # Run dispatcher polling in the background event loop
        asyncio.create_task(dp.start_polling(bot))

    # Setup scheduler jobs
    # Poll battles every minute
    scheduler.add_job(poll_active_battles, 'interval', seconds=settings.BATTLE_POLL_INTERVAL, id='poll_battles', replace_existing=True)
    # Check SRS reviews once a day (at 9 AM)
    scheduler.add_job(check_srs_reviews, 'cron', hour=9, minute=0, id='srs_reviews', replace_existing=True)
    # Poll LeetCode challenge and contests every 5 minutes
    scheduler.add_job(poll_leetcode_feed, 'interval', minutes=5, id='poll_leetcode_feed', replace_existing=True)

    scheduler.start()
    logger.info("Scheduler started.")

    # Run LeetCode feed poll immediately on startup in a background task
    asyncio.create_task(poll_leetcode_feed())

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
                    chat_id=channel_id,
                    text=public_msg,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to send startup message to channel {channel_id}: {e}", exc_info=True)



    yield

    # Shutdown logic
    scheduler.shutdown()
    logger.info("Scheduler shutdown.")
    await bot.session.close()
    await leetcode_client.close()
    await cache_manager.close()
    await db.close()


app = FastAPI(lifespan=lifespan)


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
        "database": "connected" if db.pool else "disconnected"
    }


if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=settings.PORT, reload=False)
