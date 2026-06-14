import logging
import asyncio
from aiogram import Router, html
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from src.services.supabase_db import db
from src.services.redis_cache import cache_manager
from src.utils.roles import RoleFilter, UserRole, get_user_role
from src.config import settings

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("setrole"), RoleFilter(UserRole.SUPER_ADMIN))
async def cmd_setrole(message: Message, command: CommandObject):
    """
    Promote or demote a target user to COORDINATOR or USER.
    Only SUPER_ADMINs can run this. SUPER_ADMINs cannot demote other SUPER_ADMINs.
    """
    if not command.args or len(command.args.split()) != 2:
        await message.reply(f"⚠️ Usage: {html.code(html.quote('/setrole <telegram_id_or_username> <COORDINATOR/USER>'))}", parse_mode="HTML")
        return

    identifier, new_role = command.args.split()
    new_role = new_role.upper()

    if new_role not in ["COORDINATOR", "USER"]:
        await message.reply("❌ Invalid role. Supported roles: `COORDINATOR` or `USER`.")
        return

    target_user = await db.get_user_by_id_or_username(identifier)
    if not target_user:
        await message.reply(f"❌ User <b>{html.quote(identifier)}</b> not found in database.", parse_mode="HTML")
        return

    target_user_id = target_user["telegram_id"]

    # Prevent demoting/modifying a SUPER_ADMIN
    if target_user_id in settings.super_admin_ids:
        await message.reply("❌ Cannot modify roles of a Super Admin.")
        return

    # Update role in DB
    await db.execute("UPDATE users SET role = $1 WHERE telegram_id = $2", new_role, target_user_id)

    # Invalidate Redis role cache for all chats containing the user
    try:
        keys = await cache_manager.client.keys(f"user:role:*:{target_user_id}")
        if keys:
            await cache_manager.client.delete(*keys)
    except Exception as e:
        logger.error(f"Error evicting role cache for user {target_user_id}: {e}")

    await message.reply(
        f"✅ Successfully updated user {html.bold(target_user['first_name'] or target_user['username'] or str(target_user_id))}'s role to {html.bold(new_role)}.",
        parse_mode="HTML"
    )

@router.message(Command("maintenance"), RoleFilter(UserRole.SUPER_ADMIN))
async def cmd_maintenance(message: Message, command: CommandObject):
    """
    Toggle maintenance mode.
    Only SUPER_ADMINs can run this.
    """
    if not command.args:
        # Show current maintenance status
        is_maintenance = await cache_manager.get("system:maintenance")
        status = "ENABLED 🛠️" if str(is_maintenance) == "1" else "DISABLED ✅"
        await message.reply(f"Maintenance status: <b>{status}</b>", parse_mode="HTML")
        return

    arg = command.args.strip().lower()
    if arg == "on":
        await cache_manager.set("system:maintenance", "1", expire_seconds=86400 * 30)  # Active for 30 days
        await message.reply("🛠️ Maintenance mode has been <b>ENABLED</b>. Regular users are now blocked.", parse_mode="HTML")
    elif arg == "off":
        await cache_manager.delete("system:maintenance")
        await message.reply("✅ Maintenance mode has been <b>DISABLED</b>. Regular users can now interact with the bot.", parse_mode="HTML")
    else:
        await message.reply("⚠️ Usage: `/maintenance [on/off]`", parse_mode="HTML")

@router.message(Command("broadcast"), RoleFilter(UserRole.SUPER_ADMIN))
async def cmd_broadcast(message: Message, command: CommandObject):
    """
    Broadcasts HTML message to all registered users in private DMs.
    """
    if not command.args:
        await message.reply("⚠️ Usage: `/broadcast <message>`", parse_mode="HTML")
        return

    broadcast_msg = command.args.strip()

    # Get all registered user IDs from database
    rows = await db.fetch("SELECT telegram_id FROM users")
    user_ids = [r["telegram_id"] for r in rows]

    await message.reply(f"🚀 Starting broadcast to {len(user_ids)} users. Please wait...")

    success = 0
    fail = 0

    # Batch sending to prevent rate limits: 30 per second
    for i, user_id in enumerate(user_ids):
        try:
            await message.bot.send_message(
                chat_id=user_id,
                text=broadcast_msg,
                parse_mode="HTML"
            )
            success += 1
        except Exception as err:
            logger.debug(f"Failed broadcast to {user_id}: {err}")
            fail += 1

        # Rate limit control: sleep 1.0s every 30 messages
        if (i + 1) % 30 == 0:
            await asyncio.sleep(1.0)
        else:
            await asyncio.sleep(0.035)

    await message.reply(
        f"📢 {html.bold('Broadcast Complete!')}\n\n"
        f"✅ Success: {success}\n"
        f"❌ Failed/Blocked: {fail}",
        parse_mode="HTML"
    )

@router.message(Command("pban"), RoleFilter(UserRole.COORDINATOR))
async def cmd_pban(message: Message, command: CommandObject):
    """
    Globally bans a user.
    """
    if not command.args:
        await message.reply(f"⚠️ Usage: {html.code(html.quote('/pban <telegram_id_or_username> [reason]'))}", parse_mode="HTML")
        return

    args = command.args.split()
    identifier = args[0]
    reason = " ".join(args[1:]) if len(args) > 1 else "No reason provided."

    target_user = await db.get_user_by_id_or_username(identifier)
    if not target_user:
        await message.reply(f"❌ User <b>{html.quote(identifier)}</b> not found in database.", parse_mode="HTML")
        return

    target_id = target_user["telegram_id"]

    if target_id in settings.super_admin_ids:
        await message.reply("❌ Cannot pban a Super Admin.")
        return

    # Resolve roles
    bot = message.bot
    target_role = await get_user_role(
        user_id=target_id,
        chat_id=message.chat.id,
        chat_type=message.chat.type,
        bot=bot
    )

    caller_role = await get_user_role(
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        chat_type=message.chat.type,
        bot=bot
    )

    if caller_role == UserRole.COORDINATOR and target_role >= UserRole.COORDINATOR:
        await message.reply("❌ Coordinators cannot pban other Coordinators or Super Admins.")
        return

    # Update DB
    await db.execute("UPDATE users SET is_banned = TRUE WHERE telegram_id = $1", target_id)

    # Set banned cache in Redis
    cache_key = f"user:banned:{target_id}"
    await cache_manager.set(cache_key, "1", expire_seconds=86400 * 365) # cache for 1 year

    # Send ban notice in DMs to the target user if possible
    try:
        await message.bot.send_message(
            chat_id=target_id,
            text=f"❌ You have been globally banned from using the LeetCode Companion bot.\nReason: <i>{html.quote(reason)}</i>",
            parse_mode="HTML"
        )
    except Exception:
        pass

    # Log action to log channel
    from src.utils.logging_helper import log_admin_activity
    actor_username = message.from_user.username or message.from_user.first_name or str(message.from_user.id)
    target_username = target_user['username'] or target_user['first_name'] or str(target_id)
    log_text = (
        f"🚨 {html.bold('User Globally Banned')} 🚨\n\n"
        f"• {html.bold('Target User:')} {html.bold(target_username)} ({html.code(str(target_id))})\n"
        f"• {html.bold('Banned by:')} @{actor_username} ({html.code(str(message.from_user.id))})\n"
        f"• {html.bold('Reason:')} {html.italic(html.quote(reason))}"
    )
    await log_admin_activity(log_text, message)

    await message.reply(
        f"✅ Successfully banned {html.bold(target_user['first_name'] or target_user['username'] or str(target_id))}.\nReason: {html.italic(reason)}",
        parse_mode="HTML"
    )

@router.message(Command("unpban"), RoleFilter(UserRole.COORDINATOR))
async def cmd_unpban(message: Message, command: CommandObject):
    """
    Globally unbans a user.
    """
    if not command.args:
        await message.reply(f"⚠️ Usage: {html.code(html.quote('/unpban <telegram_id_or_username>'))}", parse_mode="HTML")
        return

    identifier = command.args.strip()

    target_user = await db.get_user_by_id_or_username(identifier)
    if not target_user:
        await message.reply(f"❌ User <b>{html.quote(identifier)}</b> not found in database.", parse_mode="HTML")
        return

    target_id = target_user["telegram_id"]

    # Update DB
    await db.execute("UPDATE users SET is_banned = FALSE WHERE telegram_id = $1", target_id)

    # Evict cache key
    cache_key = f"user:banned:{target_id}"
    await cache_manager.delete(cache_key)

    # Notify user in DM if possible
    try:
        await message.bot.send_message(
            chat_id=target_id,
            text="✅ Your global ban has been lifted. You can now use the bot again!",
            parse_mode="HTML"
        )
    except Exception:
        pass

    # Log action to log channel
    from src.utils.logging_helper import log_admin_activity
    actor_username = message.from_user.username or message.from_user.first_name or str(message.from_user.id)
    target_username = target_user['username'] or target_user['first_name'] or str(target_id)
    log_text = (
        f"✅ {html.bold('User Globally Unbanned')} ✅\n\n"
        f"• {html.bold('Target User:')} {html.bold(target_username)} ({html.code(str(target_id))})\n"
        f"• {html.bold('Unbanned by:')} @{actor_username} ({html.code(str(message.from_user.id))})"
    )
    await log_admin_activity(log_text, message)

    await message.reply(
        f"✅ Successfully unbanned {html.bold(target_user['first_name'] or target_user['username'] or str(target_id))}.",
        parse_mode="HTML"
    )

@router.message(Command("forceverify"), RoleFilter(UserRole.COORDINATOR))
async def cmd_forceverify(message: Message, command: CommandObject):
    """
    Link and verify a LeetCode username bypass validation checks.
    """
    if not command.args or len(command.args.split()) != 2:
        await message.reply(f"⚠️ Usage: {html.code(html.quote('/forceverify <telegram_id_or_username> <leetcode_username>'))}", parse_mode="HTML")
        return

    identifier, leetcode_user = command.args.split()

    target_user = await db.get_user_by_id_or_username(identifier)
    if not target_user:
        await message.reply(f"❌ User <b>{html.quote(identifier)}</b> not found in database.", parse_mode="HTML")
        return

    target_id = target_user["telegram_id"]

    # Link and verify
    await db.link_leetcode_account(target_id, leetcode_user, "FORCE_VERIFIED")
    await db.verify_leetcode_account(target_id)

    # Log action to log channel
    from src.utils.logging_helper import log_admin_activity
    actor_username = message.from_user.username or message.from_user.first_name or str(message.from_user.id)
    target_username = target_user['username'] or target_user['first_name'] or str(target_id)
    log_text = (
        f"🔗 {html.bold('User Force-Verified')} 🔗\n\n"
        f"• {html.bold('Target User:')} {html.bold(target_username)} ({html.code(str(target_id))})\n"
        f"• {html.bold('LeetCode Username:')} {html.bold(leetcode_user)}\n"
        f"• {html.bold('Force-verified by:')} @{actor_username} ({html.code(str(message.from_user.id))})"
    )
    await log_admin_activity(log_text, message)

    await message.reply(
        f"✅ Successfully force-verified {html.bold(target_user['first_name'] or target_user['username'] or str(target_id))}'s LeetCode account as {html.bold(leetcode_user)}.",
        parse_mode="HTML"
    )

@router.message(Command("userinfo"), RoleFilter(UserRole.COORDINATOR))
async def cmd_userinfo(message: Message, command: CommandObject):
    """
    Get user metadata, roles, link and active battles.
    """
    if not command.args:
        await message.reply(f"⚠️ Usage: {html.code(html.quote('/userinfo <telegram_id_or_username>'))}", parse_mode="HTML")
        return

    identifier = command.args.strip()

    target_user = await db.get_user_by_id_or_username(identifier)
    if not target_user:
        await message.reply(f"❌ User <b>{html.quote(identifier)}</b> not found in database.", parse_mode="HTML")
        return

    target_id = target_user["telegram_id"]

    # Fetch LeetCode link
    link = await db.get_linked_account(target_id)
    lc_profile = f"@{link['leetcode_username']} (Verified)" if link and link.get("verified") else f"@{link['leetcode_username']} (Unverified)" if link else "Not linked"

    # Fetch user resolved role in private context
    role = await get_user_role(target_id, target_id, "private", message.bot)

    # Fetch active battle info
    active_battles = await db.fetch(
        "SELECT id, problem_title, status FROM battles WHERE (challenger_id = $1 OR opponent_id = $1) AND status IN ('ACTIVE', 'PAUSED')",
        target_id
    )
    
    battles_str = ""
    if active_battles:
        for b in active_battles:
            battles_str += f"\n   • ⚔️ {html.bold(b['problem_title'])} (Status: {b['status']})\n     UUID: {html.code(str(b['id']))}"
    else:
        battles_str = " None"

    info_msg = (
        f"👤 {html.bold('User Information Summary')} 👤\n\n"
        f"• {html.bold('First Name:')} {target_user['first_name'] or 'N/A'}\n"
        f"• {html.bold('Username:')} @{target_user['username'] or 'N/A'}\n"
        f"• {html.bold('Telegram ID:')} {html.code(target_id)}\n"
        f"• {html.bold('Global Role:')} {html.bold(role.name)} ({target_user.get('role', 'USER')})\n"
        f"• {html.bold('Ban Status:')} {'🚨 Banned' if target_user.get('is_banned') else '✅ Active'}\n"
        f"• {html.bold('LeetCode Account:')} {lc_profile}\n"
        f"• {html.bold('Stats:')} Level {target_user.get('level', 1)} • {target_user.get('xp', 0)} XP • {target_user.get('coins', 0)} Coins\n"
        f"• {html.bold('Active Battles:')}{battles_str}"
    )

    await message.reply(info_msg, parse_mode="HTML")

@router.message(Command("activebattles"), RoleFilter(UserRole.COORDINATOR))
async def cmd_activebattles(message: Message):
    """
    List all currently active or paused battles.
    """
    battles = await db.fetch("SELECT * FROM battles WHERE status IN ('ACTIVE', 'PAUSED') ORDER BY created_at DESC")
    if not battles:
        await message.reply("ℹ️ There are no active or paused battles currently.")
        return

    msg = f"⚔️ {html.bold('Current Active/Paused Battles:')} ⚔️\n\n"
    for idx, b in enumerate(battles, start=1):
        # Fetch usernames
        c_row = await db.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", b["challenger_id"])
        o_row = await db.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", b["opponent_id"])
        c_name = c_row["first_name"] or c_row["username"] or str(b["challenger_id"])
        o_name = o_row["first_name"] or o_row["username"] or str(b["opponent_id"])
        
        status_emoji = "⏸️" if b["status"] == "PAUSED" else "⚔️"
        msg += (
            f"{idx}. {status_emoji} {html.bold(c_name)} vs {html.bold(o_name)}\n"
            f"   🏆 Problem: {b['problem_title']}\n"
            f"   UUID: {html.code(str(b['id']))}\n"
            f"   Status: {html.bold(b['status'])}\n\n"
        )

    await message.reply(msg, parse_mode="HTML")
