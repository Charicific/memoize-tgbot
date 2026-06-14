from enum import IntEnum
import logging
from aiogram.filters import BaseFilter
from aiogram.types import Message
from aiogram import Bot

logger = logging.getLogger(__name__)

class UserRole(IntEnum):
    USER = 0            # Default regular user / group member
    GROUP_ADMIN = 1     # Group administrator (contextual)
    GROUP_OWNER = 2     # Group owner / creator (contextual - higher group level authority)
    COORDINATOR = 3     # Global coordinator (stored in DB)
    SUPER_ADMIN = 4     # Global super admin (defined in .env list)

async def get_user_role(user_id: int, chat_id: int, chat_type: str, bot: Bot) -> UserRole:
    """
    Dynamically resolves the role of a user based on static config, database, and Telegram chat permissions.
    Caches the resolved role in Redis to prevent database and Telegram API call overhead.
    """
    # 1. Check if SUPER_ADMIN
    from src.config import settings
    if user_id in settings.super_admin_ids:
        return UserRole.SUPER_ADMIN

    # 2. Check Redis cache first
    from src.services.redis_cache import cache_manager
    cache_key = f"user:role:{chat_id}:{user_id}"
    try:
        cached_val = await cache_manager.get(cache_key)
        if cached_val is not None:
            return UserRole(int(cached_val))
    except Exception as cache_err:
        logger.error(f"Error checking user role cache: {cache_err}")

    # 3. Check if COORDINATOR (DB check)
    from src.services.supabase_db import db
    role = UserRole.USER
    try:
        user_db = await db.get_user(user_id)
        if user_db and user_db.get("role") == "COORDINATOR":
            role = UserRole.COORDINATOR
    except Exception as db_err:
        logger.error(f"Error checking user role in DB: {db_err}")

    # 4. Check if Group Owner or Admin (in group/supergroup context)
    if role < UserRole.COORDINATOR and chat_type in ["group", "supergroup"]:
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status == "creator":
                role = UserRole.GROUP_OWNER
            elif member.status == "administrator":
                role = UserRole.GROUP_ADMIN
        except Exception as tg_err:
            logger.debug(f"Failed to get chat member status: {tg_err}")

    # 5. Cache result for 5 minutes (300 seconds)
    try:
        await cache_manager.set(cache_key, str(role.value), expire_seconds=300)
    except Exception as cache_err:
        logger.error(f"Error writing user role cache: {cache_err}")

    return role

class RoleFilter(BaseFilter):
    """
    Filter to check if the user meets the minimum role required to access a handler.
    """
    def __init__(self, min_role: UserRole):
        self.min_role = min_role

    async def __call__(self, message: Message, bot: Bot) -> bool:
        if not message.from_user:
            return False
        
        user_role = await get_user_role(
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            chat_type=message.chat.type,
            bot=bot
        )
        return user_role >= self.min_role
