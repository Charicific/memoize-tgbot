import logging
import datetime
from aiogram import Router, F, html
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from src.services.supabase_db import db
from src.services.leetcode import LeetCodeClient
from src.services.redis_cache import cache_manager

router = Router()
logger = logging.getLogger(__name__)

leetcode_client = LeetCodeClient()

@router.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message):
    user_id = message.from_user.id
    if await cache_manager.is_rate_limited(user_id, "leaderboard", limit=5, period=10):
        await message.reply("Slow down. Caching leaderboard...")
        return

    # Check cache
    cache_key = "global_leaderboard"
    cached = await cache_manager.get(cache_key)
    if cached:
        await message.reply(cached, parse_mode="HTML")
        return

    users = await db.get_global_leaderboard(limit=10)
    if not users:
        await message.reply("🏆 No users on the leaderboard yet. Solve problems to get listed!")
        return

    response = f"🏆 {html.bold('LeetCode Companion Leaderboard')} 🏆\n\n"
    for rank, u in enumerate(users, start=1):
        name = u['first_name'] or u['username'] or f"User {u['telegram_id']}"
        username_str = f" (@{u['username']})" if u['username'] else ""
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"
        response += f"{medal} {html.bold(name)}{username_str}\n   ✨ Level {u['level']} • {u['xp']} XP • {u['coins']} coins\n\n"

    # Cache for 5 minutes
    await cache_manager.set(cache_key, response, expire_seconds=300)
    await message.reply(response, parse_mode="HTML")


@router.message(Command("battle"))
async def cmd_battle(message: Message, command: CommandObject):
    user_id = message.from_user.id
    
    if await cache_manager.is_rate_limited(user_id, "battle", limit=3, period=15):
        await message.reply("Please wait a bit before challenging someone else.")
        return

    # Challenger must be linked
    challenger_link = await db.get_linked_account(user_id)
    if not challenger_link or not challenger_link["verified"]:
        await message.reply("⚠️ You must link and verify your own LeetCode account first using `/link <username>`!")
        return

    if not command.args:
        await message.reply("⚠️ Please tag the friend you want to challenge:\nExample: `/battle @username`", parse_mode="HTML")
        return

    opponent_username = command.args.strip().replace("@", "")
    
    # Fetch opponent from database
    # We look up the opponent by their telegram username
    opponent_row = await db.fetchrow("SELECT * FROM users WHERE username = $1", opponent_username)
    if not opponent_row:
        await message.reply(
            f"❌ Could not find user {html.bold('@' + opponent_username)} in our system.\n"
            f"Please make sure they have started the bot by clicking /start.",
            parse_mode="HTML"
        )
        return

    opponent_id = opponent_row["telegram_id"]
    if opponent_id == user_id:
        await message.reply("😅 You cannot challenge yourself to a battle!")
        return

    # Opponent must be linked
    opponent_link = await db.get_linked_account(opponent_id)
    if not opponent_link or not opponent_link["verified"]:
        await message.reply(f"❌ Your opponent {html.bold('@' + opponent_username)} has not linked their LeetCode profile yet.", parse_mode="HTML")
        return

    # Setup a random medium problem for the battle
    await message.reply("🎲 Selecting a battle problem... Please wait.")
    problems = await leetcode_client.get_problemset_questions(limit=50, difficulty="medium")
    free_problems = [p for p in problems if not p.get("isPaidOnly")]
    
    if not free_problems:
        await message.reply("❌ Error picking a battle problem. Please try again.")
        return

    selected_prob = random.choice(free_problems)
    problem_slug = selected_prob["titleSlug"]
    problem_title = selected_prob["title"]

    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)

    # Save battle request in database
    battle = await db.create_battle(user_id, opponent_id, problem_slug, problem_title, expires_at)
    battle_id = battle["id"]

    # Send challenge message
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚔️ Accept", callback_data=f"battle_accept:{battle_id}"),
            InlineKeyboardButton(text="🏳️ Decline", callback_data=f"battle_decline:{battle_id}")
        ]
    ])

    challenge_msg = (
        f"⚔️ {html.bold('LeetCode Battle Challenge!')} ⚔️\n\n"
        f"👤 challenger: {html.bold(message.from_user.first_name or message.from_user.username)}\n"
        f"👤 Opponent: {html.bold('@' + opponent_username)}\n\n"
        f"🏆 Problem: {html.bold(problem_title)} (Medium)\n"
        f"⏳ Time Limit: {html.bold('60 minutes')} once started\n\n"
        f"@{opponent_username}, do you accept this challenge?"
    )

    await message.bot.send_message(
        chat_id=opponent_id,
        text=challenge_msg,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await message.reply(f"✅ Battle request sent to {html.bold('@' + opponent_username)}! Waiting for their response.", parse_mode="HTML")


@router.callback_query(F.data.startswith("battle_accept:"))
async def process_battle_accept(callback_query: CallbackQuery):
    battle_id = callback_query.data.split(":")[1]
    
    battle = await db.get_battle(battle_id)
    if not battle:
        await callback_query.answer("⚠️ Battle not found.", show_alert=True)
        return

    if battle["status"] != "PENDING":
        await callback_query.answer(f"⚠️ This challenge is already {battle['status'].lower()}.", show_alert=True)
        return

    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = now + datetime.timedelta(hours=1)

    # Start the battle
    await db.update_battle_status(battle_id, "ACTIVE", started_at=now)
    # Update expiration time to 60 mins from now
    await db.execute("UPDATE battles SET expires_at = $2 WHERE id = $1::uuid", battle_id, expires_at)

    challenger_row = await db.fetchrow("SELECT username FROM users WHERE telegram_id = $1", battle["challenger_id"])
    challenger_name = challenger_row["username"] if challenger_row else "Challenger"

    battle_url = f"https://leetcode.com/problems/{battle['problem_slug']}"

    start_msg = (
        f"⚔️ {html.bold('Battle Started!')} ⚔️\n\n"
        f"🏆 Problem: <a href='{battle_url}'>{battle['problem_title']}</a> (Medium)\n"
        f"⏱️ Deadline: {html.code('60 minutes')} from now\n\n"
        f"🚀 Solve the problem on LeetCode and submit it.\n"
        f"The first one to get a green accepted submission wins!\n\n"
        f"We will automatically poll LeetCode for results. Good luck!"
    )

    # Notify opponent (who clicked accept)
    await callback_query.message.edit_text(start_msg, parse_mode="HTML", disable_web_page_preview=True)
    
    # Notify challenger
    await callback_query.message.bot.send_message(
        chat_id=battle["challenger_id"],
        text=f"⚔️ Your challenge to @{callback_query.from_user.username} was accepted!\n\n" + start_msg,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

    await callback_query.answer("Battle accepted!")


@router.callback_query(F.data.startswith("battle_decline:"))
async def process_battle_decline(callback_query: CallbackQuery):
    battle_id = callback_query.data.split(":")[1]
    
    battle = await db.get_battle(battle_id)
    if not battle:
        await callback_query.answer("⚠️ Battle not found.", show_alert=True)
        return

    if battle["status"] != "PENDING":
        await callback_query.answer("⚠️ This challenge is no longer pending.", show_alert=True)
        return

    await db.update_battle_status(battle_id, "DECLINED")

    await callback_query.message.edit_text("❌ You have declined the battle challenge.")
    
    # Notify challenger
    opponent_name = callback_query.from_user.username or callback_query.from_user.first_name
    await callback_query.message.bot.send_message(
        chat_id=battle["challenger_id"],
        text=f"😔 Your battle challenge was declined by @{opponent_name}."
    )

    await callback_query.answer("Battle declined.")
