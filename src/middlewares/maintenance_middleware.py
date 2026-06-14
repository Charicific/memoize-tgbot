import logging
from aiogram import BaseMiddleware, types
from src.services.redis_cache import cache_manager
from src.utils.roles import get_user_role, UserRole

logger = logging.getLogger(__name__)

class MaintenanceCheckMiddleware(BaseMiddleware):
    """
    Middleware that intercepts updates when the bot is in maintenance mode.
    Only SUPER_ADMIN and COORDINATOR bypass maintenance.
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
            # 1. Skip checks for Super Admins (zero Redis/DB hits)
            from src.config import settings
            if user_id in settings.super_admin_ids:
                return await handler(event, data)

            # 2. Check if maintenance mode is enabled in Redis
            try:
                is_maintenance = await cache_manager.get("system:maintenance")
            except Exception as cache_err:
                logger.error(f"Redis cache error in MaintenanceCheckMiddleware: {cache_err}")
                is_maintenance = None

            if str(is_maintenance) == "1":
                # Maintenance mode active. Resolve target's role.
                bot = data.get("bot")
                chat_id = user_event.chat.id if isinstance(user_event, types.Message) else user_event.message.chat.id if user_event.message else user_id
                chat_type = user_event.chat.type if isinstance(user_event, types.Message) else user_event.message.chat.type if user_event.message else "private"

                try:
                    role = await get_user_role(
                        user_id=user_id,
                        chat_id=chat_id,
                        chat_type=chat_type,
                        bot=bot
                    )
                except Exception as role_err:
                    logger.error(f"Error checking user role in MaintenanceCheckMiddleware: {role_err}")
                    role = UserRole.USER

                # Only Coordinator and Super Admin bypass maintenance
                if role < UserRole.COORDINATOR:
                    maintenance_msg = "🛠️ The bot is currently undergoing scheduled maintenance. Please try again later."
                    if isinstance(user_event, types.Message):
                        try:
                            await user_event.reply(maintenance_msg)
                        except Exception:
                            pass
                    elif isinstance(user_event, types.CallbackQuery):
                        try:
                            await user_event.answer(maintenance_msg, show_alert=True)
                        except Exception:
                            pass
                    return

        return await handler(event, data)
