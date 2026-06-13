import asyncio
import logging
import datetime
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, html, types
from aiogram.fsm.storage.redis import RedisStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from src.config import settings
from src.services.supabase_db import db
from src.services.redis_cache import cache_manager
from src.services.leetcode import LeetCodeClient
from src.handlers import get_main_router

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Initialize clients
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher(storage=cache_manager.fsm_storage)
leetcode_client = LeetCodeClient()

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
        logger.error(f"Error in poll_active_battles: {e}")


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
        logger.error(f"Error checking SRS reviews: {e}")


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

    scheduler.start()
    logger.info("Scheduler started.")

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
        logger.error(f"Webhook update processing error: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/health")
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
