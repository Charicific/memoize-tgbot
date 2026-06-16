import random
import logging
import time
from html import escape as html_escape
from aiogram import Router, html, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, ChatMemberUpdated, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from src.services.supabase_db import db
from src.services.leetcode import LeetCodeClient
from src.services.redis_cache import cache_manager
from src.utils.logging_helper import send_log
from src.utils.formatters import clean_leetcode_html
from src.utils.roles import RoleFilter, UserRole

router = Router()
logger = logging.getLogger(__name__)

# Reusable client instanced locally or dynamically
leetcode_client = LeetCodeClient()


@router.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    # Check if rate limited
    if await cache_manager.is_rate_limited(user_id, "start", limit=3, period=10):
        await message.reply("Please don't spam. Wait a few seconds.")
        return

    # Check start parameters first (e.g. start=daily)
    if command.args and command.args.startswith("daily"):
        # Auto-create user record in case they haven't started the bot yet
        await db.create_user(user_id, username, first_name)
        
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

        clean_description = clean_leetcode_html(content, max_length=2000)
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
        await message.reply(response, parse_mode="HTML", disable_web_page_preview=True)
        return

    # Check if user already exists
    existing_user = await db.get_user(user_id)

    # Create user in database
    await db.create_user(user_id, username, first_name)

    # Log new user starting the bot
    if not existing_user:
        user_link = f"tg://user?id={user_id}"
        mention = f"<a href='{user_link}'>{html_escape(first_name or 'User')}</a>"
        if username:
            mention += f" (@{html_escape(username)})"

        log_text = (
            f"🆕 {html.bold('New User Started Bot')}\n\n"
            f"👤 {html.bold('User:')} {mention}\n"
            f"🆔 {html.bold('Telegram ID:')} {html.code(user_id)}"
        )
        await send_log(log_text)

    welcome_text = (
        f"👋 Welcome {html.bold(first_name or 'there')} to the {html.bold('LeetCode Companion Bot')}!\n\n"
        "I will help you build discipline, track your spaced repetition reviews, compete with friends, "
        "and get AI help right inside Telegram.\n\n"
        f"🚀 {html.bold('Get started:')}\n"
        f"1. Link your LeetCode profile: {html.code('/link &lt;username&gt;')}\n"
        "2. Add the verification code to your LeetCode profile ReadMe.\n"
        "3. Run `/verify` to complete linking!\n\n"
        "Type `/help` to see all available commands."
    )
    await message.reply(welcome_text, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        f"📚 {html.bold('Available Commands:')}\n\n"
        
        f"⚙️ {html.bold('Profile & Accounts:')}\n"
        f"• `/start` — Start onboarding and welcome message\n"
        f"• `/help` — Show this comprehensive command guide\n"
        f"• {html.code('/link &lt;leetcode_username&gt;')} — Connect your LeetCode profile\n"
        f"• `/verify` — Verify ownership via LeetCode bio code\n"
        f"• `/unlink` — Disconnect your LeetCode profile\n"
        f"• `/profile` — View level, XP, coins, and LeetCode stats\n"
        f"• `/myrole` — Check your permission level in this chat\n\n"
        
        f"⚔️ {html.bold('Practice & Competitions:')}\n"
        f"• `/daily` — Fetch today's LeetCode Daily Challenge\n"
        f"• {html.code('/random [difficulty] [tag]')} — Get a random free problem\n"
        f"• `/contest` — List upcoming LeetCode contests\n\n"
        
        f"🧠 {html.bold('Spaced Repetition (SRS):')}\n"
        f"• {html.code('/solved [slug] [quality]')} — Log solved problem & schedule review (0-5 scale)\n\n"
        
        f"🔥 {html.bold('Coding Streaks:')}\n"
        f"• `/streak` — View LeetCode calendar submission streak\n"
        f"• `/dstreak` — View local Daily Challenge solve streak\n\n"
        
        f"🤖 {html.bold('AI Features:')}\n"
        f"• {html.code('/hint &lt;problem_slug&gt;')} — Get progressive tips for a problem (Llama 3.3)\n"
        f"• {html.code('/analyze &lt;paste_code&gt;')} — Time/space complexity analysis (Llama 3.3)\n"
        f"• {html.code('/review &lt;paste_code&gt;')} — Code quality audit (Gemini Flash 2.0)\n"
        f"• {html.code('/visualize &lt;paste_code&gt;')} — Flowchart & variable trace (Llama 3.3)\n\n"
        
        f"🔔 {html.bold('Settings & Reminders:')}\n"
        f"• `/reminders` — Manage daily challenge, streak, and contest alerts\n\n"
        
        f"📊 {html.bold('Leaderboards:')}\n"
        f"• `/leaderboard` — View group XP leaderboard\n"
        f"• `/gleaderboard` — View global XP leaderboard\n\n"
        
        f"🎮 {html.bold('Coding Battles:')}\n"
        f"• {html.code('/battle @username')} — Challenge a friend to 1v1 battle\n"
        f"• {html.code('/battle open [difficulty] [tag]')} — Create group battle lobby\n"
        f"• `/stopbattle` — Propose draw (1v1) or cancel battle (Group host/admin)\n"
        f"• `/pausebattle` — Propose pause (1v1) or freeze timer (Group host/admin)\n"
        f"• `/resumebattle` — Propose resume (1v1) or restart timer (Group host/admin)\n\n"
        
        f"🛡️ {html.bold('Group Moderation:')}\n"
        f"• {html.code('/config_group &lt;setting&gt; &lt;value&gt;')} — Toggle battles/feed settings\n"
        f"• {html.code('/mute_battle @username &lt;on/off&gt;')} — Mute/unmute member from battles\n"
        f"• `/clear_group_history` — Reset group leaderboard stats"
    )
    await message.reply(help_text, parse_mode="HTML")


@router.message(Command("ping"), RoleFilter(UserRole.COORDINATOR))
async def cmd_ping(message: Message):
    # Measure DB latency
    start_db = time.time()
    try:
        await db.fetchrow("SELECT 1")
        db_latency = f"{int((time.time() - start_db) * 1000)}ms"
    except Exception as e:
        db_latency = f"Error ({e})"

    # Measure Telegram API latency
    start_tg = time.time()
    sent_msg = await message.reply("🏓 Ponging...")
    tg_latency = int((time.time() - start_tg) * 1000)

    # Edit message with final metrics
    status_text = (
        f"🏓 {html.bold('Pong!')}\n\n"
        f"⚡ {html.bold('Telegram Bot API:')} {tg_latency}ms\n"
        f"💾 {html.bold('Database Latency:')} {db_latency}"
    )
    await sent_msg.edit_text(status_text, parse_mode="HTML")


@router.message(Command("stats"), RoleFilter(UserRole.COORDINATOR))
async def cmd_stats(message: Message):
    try:
        stats = await db.get_bot_stats()
    except Exception as e:
        logger.error(f"Error executing stats query: {e}")
        await message.reply("❌ Error retrieving statistics. Please try again later.")
        return

    stats_text = (
        f"📊 {html.bold('Memoize Bot Statistics')}\n\n"
        f"👤 {html.bold('Users:')}\n"
        f"• Total registered users: {html.bold(stats['total_users'])}\n"
        f"• Linked LeetCode profiles: {html.bold(stats['total_linked'])}\n"
        f"• Verified LeetCode profiles: {html.bold(stats['total_verified'])}\n\n"
        f"⚔️ {html.bold('LeetCode Battles:')}\n"
        f"• Total battles: {html.bold(stats['total_battles'])}\n"
        f"• Active/Pending: {html.bold(stats['active_battles'])}\n"
        f"• Completed: {html.bold(stats['completed_battles'])}\n\n"
        f"🧠 {html.bold('Practice & SRS:')}\n"
        f"• Total solved problems: {html.bold(stats['total_solved'])}\n"
        f"• Active Spaced Repetition items: {html.bold(stats['total_srs'])}"
    )
    await message.reply(stats_text, parse_mode="HTML")


@router.message(Command("link"))
async def cmd_link(message: Message, command: CommandObject):
    user_id = message.from_user.id

    if await cache_manager.is_rate_limited(user_id, "link", limit=3, period=10):
        await message.reply("Please wait a moment before trying again.")
        return

    if not command.args:
        await message.reply(
            "⚠️ Please provide your LeetCode username:\nExample: `/link username`",
            parse_mode="HTML",
        )
        return

    leetcode_username = command.args.strip()

    # Generate verification code
    code = f"LC-{random.randint(1000, 9999)}"

    # Check if LeetCode user exists
    profile = await leetcode_client.get_user_profile(leetcode_username)
    if not profile:
        await message.reply(
            f"❌ Could not find a LeetCode user with username: {html.code(leetcode_username)}.\nMake sure you typed it correctly.",
            parse_mode="HTML",
        )
        return

    # Link in database (unverified)
    await db.link_leetcode_account(user_id, leetcode_username, code)

    # Log linking request
    user_link = f"tg://user?id={user_id}"
    mention = f"<a href='{user_link}'>{html_escape(message.from_user.first_name or 'User')}</a>"
    if message.from_user.username:
        mention += f" (@{html_escape(message.from_user.username)})"

    log_text = (
        f"🔗 {html.bold('LeetCode Link Requested')}\n\n"
        f"👤 {html.bold('User:')} {mention}\n"
        f"🆔 {html.bold('Telegram ID:')} {html.code(user_id)}\n"
        f"🖥️ {html.bold('LeetCode Profile:')} <a href='https://leetcode.com/{html_escape(leetcode_username)}'>{html_escape(leetcode_username)}</a>\n"
        f"🔑 {html.bold('Verification Code:')} {html.code(code)}"
    )
    await send_log(log_text)

    instructions = (
        f"🔗 {html.bold('Linking Request Received!')}\n\n"
        f"LeetCode Account: {html.bold(leetcode_username)}\n"
        f"Verification Code: {html.code(code)}\n\n"
        f"👉 To complete verification, please update your LeetCode profile Read me section to contain your verification code: {html.code(code)}\n\n"
        f"Once you've done that, run the command:\n`/verify` to complete linking."
    )
    await message.reply(instructions, parse_mode="HTML")


@router.message(Command("verify"))
async def cmd_verify(message: Message):
    user_id = message.from_user.id

    if await cache_manager.is_rate_limited(user_id, "verify", limit=3, period=15):
        await message.reply("Please wait a few seconds between verification attempts.")
        return

    link = await db.get_linked_account(user_id)
    if not link:
        await message.reply(
            f"⚠️ You haven't requested to link an account yet. Run {html.code('/link &lt;username&gt;')} first.",
            parse_mode="HTML",
        )
        return

    if link["verified"]:
        await message.reply("✅ Your LeetCode account is already verified and linked!")
        return

    leetcode_username = link["leetcode_username"]
    expected_code = link["verification_code"]

    await message.reply("🔍 Verifying your bio details... Please wait.")

    profile = await leetcode_client.get_user_profile(leetcode_username)
    if not profile or not profile.get("profile"):
        await message.reply(
            "❌ Error fetching LeetCode profile. Please try again later."
        )
        return

    bio = profile["profile"].get("aboutMe") or ""
    if expected_code in bio:
        # Success! Mark as verified
        await db.verify_leetcode_account(user_id)
        # Reward user with some starting XP & Coins
        await db.add_xp_coins(user_id, xp=50, coins=50)

        # Log verification success
        user_link = f"tg://user?id={user_id}"
        mention = f"<a href='{user_link}'>{html_escape(message.from_user.first_name or 'User')}</a>"
        if message.from_user.username:
            mention += f" (@{html_escape(message.from_user.username)})"

        log_text = (
            f"✅ {html.bold('LeetCode Account Verified')}\n\n"
            f"👤 {html.bold('User:')} {mention}\n"
            f"🆔 {html.bold('Telegram ID:')} {html.code(user_id)}\n"
            f"🖥️ {html.bold('LeetCode Profile:')} <a href='https://leetcode.com/{html_escape(leetcode_username)}'>{html_escape(leetcode_username)}</a>"
        )
        await send_log(log_text)

        success_text = (
            f"🎉 {html.bold('Verification Successful!')}\n\n"
            f"Your LeetCode account {html.bold(leetcode_username)} is now successfully linked to your Telegram profile!\n"
            f"🎁 You have been awarded {html.bold('50 XP')} and {html.bold('50 coins')}!"
        )
        await message.reply(success_text, parse_mode="HTML")
    else:
        await message.reply(
            f"❌ Verification failed. Could not find verification code {html.code(expected_code)} in your LeetCode biography.\n\n"
            f"Current Biography:\n{html.italic(bio or '[Empty]')}\n\n"
            f"Please ensure you copy the code {html.code(expected_code)} exactly into your biography and run `/verify` again.",
            parse_mode="HTML",
        )


@router.message(Command("unlink"))
async def cmd_unlink(message: Message):
    user_id = message.from_user.id

    if await cache_manager.is_rate_limited(user_id, "unlink", limit=3, period=10):
        await message.reply("Please wait a moment before trying again.")
        return

    link = await db.get_linked_account(user_id)
    if not link:
        await message.reply("⚠️ You do not have a linked LeetCode account.")
        return

    leetcode_username = link["leetcode_username"]

    # Delete link from database
    await db.execute("DELETE FROM linked_accounts WHERE telegram_id = $1", user_id)

    # Log action to log channel
    user_link = f"tg://user?id={user_id}"
    mention = f"<a href='{user_link}'>{html_escape(message.from_user.first_name or 'User')}</a>"
    if message.from_user.username:
        mention += f" (@{html_escape(message.from_user.username)})"

    log_text = (
        f"🔌 {html.bold('LeetCode Account Unlinked')} 🔌\n\n"
        f"• {html.bold('User:')} {mention}\n"
        f"• {html.bold('Telegram ID:')} {html.code(user_id)}\n"
        f"• {html.bold('Unlinked Account:')} <a href='https://leetcode.com/{html_escape(leetcode_username)}'>{html_escape(leetcode_username)}</a>"
    )
    await send_log(log_text)

    await message.reply(
        f"✅ Successfully unlinked LeetCode profile {html.bold(leetcode_username)} from your Telegram account.",
        parse_mode="HTML"
    )


@router.message(Command("profile"))
async def cmd_profile(message: Message):
    user_id = message.from_user.id

    user_db = await db.get_user(user_id)
    if not user_db:
        # Create user record
        user_db = await db.create_user(
            user_id, message.from_user.username, message.from_user.first_name
        )

    # Get cache first
    cache_key = f"profile_stats:{user_id}"
    cached_profile = await cache_manager.get(cache_key)

    link = await db.get_linked_account(user_id)
    leetcode_stats_str = ""

    if link and link["verified"]:
        leetcode_username = link["leetcode_username"]

        if cached_profile:
            leetcode_stats_str = cached_profile
        else:
            profile = await leetcode_client.get_user_profile(leetcode_username)
            ranking = "N/A"
            solved_str = ""
            if profile:
                ranking = profile["profile"].get("ranking", "N/A")
                submit_stats = profile.get("submitStats", {}).get("acSubmissionNum", [])

                solved_counts = {
                    item["difficulty"]: item["count"] for item in submit_stats
                }
                solved_str = (
                    f"🟢 Easy: {solved_counts.get('Easy', 0)}\n"
                    f"🟡 Medium: {solved_counts.get('Medium', 0)}\n"
                    f"🔴 Hard: {solved_counts.get('Hard', 0)}\n"
                    f"🏆 Total Solved: {solved_counts.get('All', 0)}"
                )

            # Fetch ranking rating if possible
            ranking_info = await leetcode_client.get_user_contest_ranking(
                leetcode_username
            )
            contest_str = "N/A"
            if ranking_info:
                contest_str = f"{int(ranking_info.get('rating', 0))} (Global Rank: {ranking_info.get('globalRanking', 'N/A')})"

            leetcode_stats_str = (
                f"\n\n🎮 {html.bold('LeetCode Profile')} ({html.italic(leetcode_username)}):\n"
                f"📊 Global Rank: {ranking}\n"
                f"⚔️ Contest Rating: {contest_str}\n"
                f"{solved_str}"
            )
            # Cache for 10 minutes
            await cache_manager.set(cache_key, leetcode_stats_str, expire_seconds=600)
    else:
        leetcode_stats_str = f"\n\n⚠️ {html.bold('LeetCode Account')} not linked or verified.\nUse {html.code('/link &lt;username&gt;')} to connect."

    profile_text = (
        f"👤 {html.bold('User Profile')}:\n"
        f"• Telegram ID: {html.code(user_id)}\n"
        f"• Level: {html.bold(user_db.get('level', 1))}\n"
        f"• XP: {html.bold(user_db.get('xp', 0))}\n"
        f"• Coins: {html.bold(user_db.get('coins', 0))}"
        f"{leetcode_stats_str}"
    )

    await message.reply(profile_text, parse_mode="HTML")


@router.my_chat_member()
async def on_my_chat_member_update(event: ChatMemberUpdated):
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status
    chat_type = event.chat.type

    # Only care about groups/supergroups/channels
    if chat_type not in ["group", "supergroup", "channel"]:
        return

    # Check if bot was added
    was_added = old_status in ["kicked", "left", "restricted"] and new_status in [
        "member",
        "administrator",
    ]
    # Check if bot was removed
    was_removed = old_status in ["member", "administrator"] and new_status in [
        "kicked",
        "left",
    ]

    # Retrieve user who made the change
    actor = event.from_user
    if not actor:
        return
    actor_link = f"tg://user?id={actor.id}"
    actor_mention = (
        f"<a href='{actor_link}'>{html_escape(actor.first_name or 'User')}</a>"
    )
    if actor.username:
        actor_mention += f" (@{html_escape(actor.username)})"

    chat_title = event.chat.title or "Unknown Chat"
    chat_id = event.chat.id

    if was_added:
        # Get member count if possible
        member_count = "N/A"
        try:
            member_count = await event.bot.get_chat_member_count(chat_id)
        except Exception:
            pass

        log_text = (
            f"➕ {html.bold('Bot Added to New ' + chat_type.capitalize())}\n\n"
            f"🏷️ {html.bold('Title:')} {html_escape(chat_title)}\n"
            f"🆔 {html.bold('Chat ID:')} {html.code(chat_id)}\n"
            f"👥 {html.bold('Member Count:')} {html.code(member_count)}\n"
            f"👤 {html.bold('Added By:')} {actor_mention}"
        )
        await send_log(log_text)

    elif was_removed:
        log_text = (
            f"➖ {html.bold('Bot Removed from ' + chat_type.capitalize())}\n\n"
            f"🏷️ {html.bold('Title:')} {html_escape(chat_title)}\n"
            f"🆔 {html.bold('Chat ID:')} {html.code(chat_id)}\n"
            f"👤 {html.bold('Removed By:')} {actor_mention}"
        )
        await send_log(log_text)


def get_reminders_keyboard(daily: bool, streak: bool, contests: bool) -> InlineKeyboardMarkup:
    daily_status = "✅ ON" if daily else "❌ OFF"
    streak_status = "✅ ON" if streak else "❌ OFF"
    contests_status = "✅ ON" if contests else "❌ OFF"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📅 Daily Challenge: {daily_status}", callback_data="toggle_reminder:daily")],
        [InlineKeyboardButton(text=f"🔥 Streak Warning: {streak_status}", callback_data="toggle_reminder:streak")],
        [InlineKeyboardButton(text=f"🏆 Contests: {contests_status}", callback_data="toggle_reminder:contests")],
        [InlineKeyboardButton(text=f"📥 Save & Close Menu", callback_data="toggle_reminder:close")]
    ])
    return keyboard

@router.message(Command("reminders"))
async def cmd_reminders(message: Message):
    user_id = message.from_user.id
    
    if message.chat.type != "private":
        await message.reply("🔔 Personal reminder configurations can only be customized in private chat with the bot. Send `/reminders` in DM @MemoizeLC_bot.")
        return

    user_db = await db.get_user(user_id)
    if not user_db:
        user_db = await db.create_user(user_id, message.from_user.username, message.from_user.first_name)

    daily = user_db.get("remind_daily", True)
    if daily is None: daily = True
    streak = user_db.get("remind_streak", True)
    if streak is None: streak = True
    contests = user_db.get("remind_contests", True)
    if contests is None: contests = True

    response = (
        f"🔔 {html.bold('Personal Reminder Settings')} 🔔\n\n"
        f"Manage the alerts you receive directly from the bot:\n\n"
        f"• {html.bold('Daily Challenge:')} Posts the daily LeetCode challenge when it drops.\n"
        f"• {html.bold('Streak Warning:')} Warm reminder in the evening (8:30 PM IST) if you haven't solved a problem today.\n"
        f"• {html.bold('Contest Alerts:')} Notifications for registration, 12h countdown, and contest starts.\n\n"
        f"👇 Click the buttons below to toggle your reminder choices:"
    )

    keyboard = get_reminders_keyboard(daily, streak, contests)
    await message.reply(response, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("toggle_reminder:"))
async def process_toggle_reminder(callback_query: CallbackQuery):
    action = callback_query.data.split(":")[1]
    user_id = callback_query.from_user.id
    
    if action == "close":
        try:
            await callback_query.message.edit_text("✅ Reminder settings saved successfully!")
        except TelegramBadRequest:
            pass  # Already closed / double-tap — safe to ignore
        await callback_query.answer("Settings saved.")
        return

    user_db = await db.get_user(user_id)
    if not user_db:
        await callback_query.answer("User profile not found. Send /start first.", show_alert=True)
        return

    column_map = {
        "daily": "remind_daily",
        "streak": "remind_streak",
        "contests": "remind_contests"
    }
    
    col = column_map.get(action)
    if not col:
        await callback_query.answer("Invalid callback query.")
        return

    current_val = user_db.get(col, True)
    if current_val is None: current_val = True
    new_val = not current_val
    
    await db.update_reminder_setting(user_id, col, new_val)
    
    user_db[col] = new_val
    
    if col == "remind_streak" and new_val:
        import asyncio
        from src.main import trigger_streak_reminder_for_user
        asyncio.create_task(trigger_streak_reminder_for_user(user_id))

    
    daily = user_db.get("remind_daily", True)
    if daily is None: daily = True
    streak = user_db.get("remind_streak", True)
    if streak is None: streak = True
    contests = user_db.get("remind_contests", True)
    if contests is None: contests = True
    
    response = (
        f"🔔 {html.bold('Personal Reminder Settings')} 🔔\n\n"
        f"Manage the alerts you receive directly from the bot:\n\n"
        f"• {html.bold('Daily Challenge:')} Posts the daily LeetCode challenge when it drops.\n"
        f"• {html.bold('Streak Warning:')} Warm reminder in the evening (8:30 PM IST) if you haven't solved a problem today.\n"
        f"• {html.bold('Contest Alerts:')} Notifications for registration, 12h countdown, and contest starts.\n\n"
        f"👇 Click the buttons below to toggle your reminder choices:"
    )
    
    keyboard = get_reminders_keyboard(daily, streak, contests)
    
    try:
        await callback_query.message.edit_text(response, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        pass  # Message not modified (double-tap) — safe to ignore
        
    status_str = "Enabled" if new_val else "Disabled"
    await callback_query.answer(f"{action.capitalize()} reminders {status_str.lower()}!")


@router.message(Command("myrole"))
async def cmd_myrole(message: Message):
    from aiogram import Bot
    from src.utils.roles import get_user_role
    
    # We can get bot dynamically from message context or update context in aiogram 3
    bot = message.bot
    role = await get_user_role(
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        chat_type=message.chat.type,
        bot=bot
    )
    
    await message.reply(
        f"👤 {html.bold(message.from_user.first_name or 'User')} details:\n"
        f"• Telegram ID: {html.code(message.from_user.id)}\n"
        f"• Chat Type: {html.code(message.chat.type)}\n"
        f"• Resolved Role: {html.bold(role.name)} ({role.value})",
        parse_mode="HTML"
    )

