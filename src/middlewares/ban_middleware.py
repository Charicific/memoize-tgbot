import logging
from aiogram import BaseMiddleware, types
from src.services.supabase_db import db
from src.services.redis_cache import cache_manager

logger = logging.getLogger(__name__)

class BanCheckMiddleware(BaseMiddleware):
    """
    Middleware that checks if a user is banned. Uses Redis to cache status to avoid database query overhead.
    """
    async def __call__(self, handler, event, data):
        user_id = None
        user_event = None

        if isinstance(event, types.Message) and event.from_user:
            user_id = event.from_user.id
            user_event = event
        elif isinstance(event, types.CallbackQuery) and event.from_user:
            user_id = event.from_user.id
            user_event = event

        if user_id:
            # 1. Skip checks for Super Admins
            from src.config import settings
            if user_id in settings.super_admin_ids:
                return await handler(event, data)

            # 2. Check Redis cache first
            cache_key = f"user:banned:{user_id}"
            try:
                is_banned = await cache_manager.get(cache_key)
            except Exception as cache_err:
                logger.error(f"Redis cache error in BanCheckMiddleware: {cache_err}")
                is_banned = None

            if str(is_banned) == "1":
                # Banned user: respond and drop update
                if isinstance(user_event, types.Message):
                    try:
                        await user_event.reply("❌ You are banned from using this bot.")
                    except Exception:
                        pass
                elif isinstance(user_event, types.CallbackQuery):
                    try:
                        await user_event.answer("❌ You are banned from using this bot.", show_alert=True)
                    except Exception:
                        pass
                return

            elif is_banned is None:
                # 3. Cache miss: Query DB
                try:
                    user_db = await db.get_user(user_id)
                    if user_db and user_db.get("is_banned", False):
                        await cache_manager.set(cache_key, "1", expire_seconds=300) # cache for 5 minutes
                        
                        if isinstance(user_event, types.Message):
                            try:
                                await user_event.reply("❌ You are banned from using this bot.")
                            except Exception:
                                pass
                        elif isinstance(user_event, types.CallbackQuery):
                            try:
                                await user_event.answer("❌ You are banned from using this bot.", show_alert=True)
                            except Exception:
                                pass
                        return
                    else:
                        # User is active: cache negative result for 5 minutes
                        await cache_manager.set(cache_key, "0", expire_seconds=300)
                except Exception as db_err:
                    # If DB is down/errors, don't lock out standard users
                    logger.error(f"DB lookup error in BanCheckMiddleware: {db_err}")

        return await handler(event, data)
