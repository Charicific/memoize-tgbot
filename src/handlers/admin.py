import io
import logging
import asyncio
import datetime as dt
from aiogram import Router, html
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, BufferedInputFile
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


async def _resolve_failed_chat_info(bot, chat_id: int, chat_lookup: dict):
    # Check lookup first
    info = chat_lookup.get(chat_id)
    if info:
        return info["type"], info["name"], info["username"]

    # Check type by ID sign
    if chat_id > 0:
        return "User", "Unknown User", None
    else:
        # Fallback to get_chat or database check
        try:
            chat = await bot.get_chat(chat_id)
            chat_type = chat.type.capitalize()  # "Supergroup", "Group", "Channel"
            title = chat.title
            username = chat.username
            return chat_type, title, username
        except Exception:
            # Fallback if get_chat fails (bot was kicked)
            # If not in lookup, assume it was a Group unless it's a known channel
            return "Group/Channel (Kicked)", "Unknown Title", None


async def _run_broadcast(
    bot,
    message,
    broadcast_msg: str,
    chat_ids: list,
    scope_label: str,
):
    """
    Core broadcast sender. Sends to all chat_ids, collects failures,
    and DMs the super admin a detailed failure report .txt file.
    """
    success = 0
    failures = []  # list of (chat_id, reason)

    for i, chat_id in enumerate(chat_ids):
        try:
            await bot.send_message(chat_id=chat_id, text=broadcast_msg, parse_mode="HTML")
            success += 1
        except Exception as err:
            logger.debug(f"Broadcast failed to {chat_id}: {err}")
            failures.append((chat_id, str(err)))

        # Rate limit: 30 messages per second
        if (i + 1) % 30 == 0:
            await asyncio.sleep(1.0)
        else:
            await asyncio.sleep(0.035)

    fail_count = len(failures)

    # Send completion summary
    await message.reply(
        f"📢 {html.bold('Broadcast Complete!')} ({scope_label})\n\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {fail_count}",
        parse_mode="HTML",
    )

    # Build and DM failure report if any failures
    if failures:
        # Build lookup map of chat details from DB
        db_users = []
        db_channels = []
        try:
            db_users = await db.fetch("SELECT telegram_id, username, first_name FROM users")
            db_channels = await db.fetch("SELECT channel_id, title FROM bot_channels")
        except Exception as e:
            logger.error(f"Failed to fetch broadcast target details from DB: {e}")

        chat_lookup = {}
        for r in db_users:
            chat_lookup[r["telegram_id"]] = {
                "type": "User",
                "name": r["first_name"],
                "username": r["username"],
            }
        for r in db_channels:
            chat_lookup[r["channel_id"]] = {
                "type": "Channel",
                "name": r["title"],
                "username": None,
            }

        now_str = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        initiator = f"@{message.from_user.username}" if message.from_user.username else str(message.from_user.id)
        lines = [
            "BROADCAST FAILURE REPORT",
            "=" * 40,
            f"Command scope : {scope_label}",
            f"Initiated by  : {initiator} ({message.from_user.id})",
            f"Timestamp     : {now_str}",
            f"Total targets : {len(chat_ids)}",
            f"Successful    : {success}",
            f"Failed        : {fail_count}",
            "",
            "FAILED CHATS:",
        ]
        for chat_id, reason in failures:
            chat_type, chat_name, chat_username = await _resolve_failed_chat_info(bot, chat_id, chat_lookup)
            lines += [
                "---",
                f"Chat ID   : {chat_id}",
                f"Type      : {chat_type}",
                f"Name      : {chat_name or 'N/A'}",
                f"Username  : {f'@{chat_username}' if chat_username else 'None'}",
                f"Reason    : {reason}",
            ]
        lines.append("---")
        report_bytes = "\n".join(lines).encode("utf-8")

        try:
            await bot.send_document(
                chat_id=message.from_user.id,
                document=BufferedInputFile(report_bytes, filename=f"broadcast_failures_{now_str[:10]}.txt"),
                caption=f"📋 Broadcast failure report — {fail_count} failed chats ({scope_label})",
            )
        except Exception as e:
            logger.error(f"Failed to DM failure report to initiator super admin {message.from_user.id}: {e}")


@router.message(Command("pbroadcast"), RoleFilter(UserRole.SUPER_ADMIN))
async def cmd_pbroadcast(message: Message, command: CommandObject):
    """Broadcasts to all personal DM users (private chats only)."""
    if not command.args:
        await message.reply("⚠️ Usage: <code>/pbroadcast &lt;message&gt;</code>", parse_mode="HTML")
        return
    rows = await db.fetch("SELECT telegram_id FROM users")
    chat_ids = [r["telegram_id"] for r in rows]
    await message.reply(f"🚀 Starting personal DM broadcast to {len(chat_ids)} users...")
    await _run_broadcast(message.bot, message, command.args.strip(), chat_ids, "Personal DMs")


@router.message(Command("gbroadcast"), RoleFilter(UserRole.SUPER_ADMIN))
async def cmd_gbroadcast(message: Message, command: CommandObject):
    """Broadcasts to all groups the bot is active in."""
    if not command.args:
        await message.reply("⚠️ Usage: <code>/gbroadcast &lt;message&gt;</code>", parse_mode="HTML")
        return
    rows = await db.fetch("SELECT DISTINCT group_id FROM group_members")
    chat_ids = [r["group_id"] for r in rows]
    await message.reply(f"🚀 Starting group broadcast to {len(chat_ids)} groups...")
    await _run_broadcast(message.bot, message, command.args.strip(), chat_ids, "Groups")


@router.message(Command("cbroadcast"), RoleFilter(UserRole.SUPER_ADMIN))
async def cmd_cbroadcast(message: Message, command: CommandObject):
    """Broadcasts to all channels the bot is a member of."""
    if not command.args:
        await message.reply("⚠️ Usage: <code>/cbroadcast &lt;message&gt;</code>", parse_mode="HTML")
        return
    chat_ids = await db.get_all_channels()
    await message.reply(f"🚀 Starting channel broadcast to {len(chat_ids)} channels...")
    await _run_broadcast(message.bot, message, command.args.strip(), chat_ids, "Channels")


@router.message(Command("broadcast"), RoleFilter(UserRole.SUPER_ADMIN))
async def cmd_broadcast(message: Message, command: CommandObject):
    """Broadcasts to ALL chats — personal DMs, groups, and channels."""
    if not command.args:
        await message.reply("⚠️ Usage: <code>/broadcast &lt;message&gt;</code>", parse_mode="HTML")
        return
    user_rows = await db.fetch("SELECT telegram_id FROM users")
    group_rows = await db.fetch("SELECT DISTINCT group_id FROM group_members")
    channel_ids = await db.get_all_channels()
    # Deduplicate
    all_ids = list({r["telegram_id"] for r in user_rows}
                   | {r["group_id"] for r in group_rows}
                   | set(channel_ids))
    await message.reply(f"🚀 Starting universal broadcast to {len(all_ids)} chats (users + groups + channels)...")
    await _run_broadcast(message.bot, message, command.args.strip(), all_ids, "All Chats")

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
