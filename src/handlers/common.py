import random
import logging
from aiogram import Router, html
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from src.services.supabase_db import db
from src.services.leetcode import LeetCodeClient
from src.services.redis_cache import cache_manager

router = Router()
logger = logging.getLogger(__name__)

# Reusable client instanced locally or dynamically
leetcode_client = LeetCodeClient()

@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    # Check if rate limited
    if await cache_manager.is_rate_limited(user_id, "start", limit=3, period=10):
        await message.reply("Please don't spam. Wait a few seconds.")
        return

    # Create user in database
    await db.create_user(user_id, username, first_name)

    welcome_text = (
        f"👋 Welcome {html.bold(first_name or 'there')} to the {html.bold('LeetCode Companion Bot')}!\n\n"
        "I will help you build discipline, track your spaced repetition reviews, compete with friends, "
        "and get AI help right inside Telegram.\n\n"
        f"🚀 {html.bold('Get started:')}\n"
        "1. Link your LeetCode profile: `/link <username>`\n"
        "2. Add the verification code to your LeetCode bio.\n"
        "3. Run `/verify` to complete linking!\n\n"
        "Type `/help` to see all available commands."
    )
    await message.reply(welcome_text, parse_mode="HTML")

@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        f"📚 {html.bold('Available Commands:')}\n\n"
        f"⚙️ {html.bold('Profile & Accounts:')}\n"
        "• `/link <leetcode_username>` — Link your LeetCode account\n"
        "• `/verify` — Verify ownership via LeetCode bio\n"
        "• `/profile` — View your progress, XP, coins, and LeetCode stats\n\n"
        f"⚔️ {html.bold('Practice & Competitions:')}\n"
        "• `/daily` — Fetch today's LeetCode challenge\n"
        "• `/random [difficulty] [tag]` — Get a random problem (e.g. `/random medium dp`)\n"
        "• `/contest` — Check upcoming contests and schedule alerts\n"
        "• `/battle @username` — Challenge a friend to a LeetCode battle\n\n"
        f"🧠 {html.bold('Spaced Repetition (SRS):')}\n"
        "• `/solved <problem_slug> <quality>` — Log a problem solved & schedule review (quality: 0=forgot, 5=perfect)\n\n"
        f"🤖 {html.bold('AI Features:')}\n"
        "• `/hint <problem_slug>` — Get progressive hints (Llama 3.3)\n"
        "• `/analyze <paste_code>` — Time/space complexity analysis (Llama 3.3)\n"
        "• `/review <paste_code>` — Full structural code review (Gemini Flash 2.0)"
    )
    await message.reply(help_text, parse_mode="HTML")

@router.message(Command("link"))
async def cmd_link(message: Message, command: CommandObject):
    user_id = message.from_user.id
    
    if await cache_manager.is_rate_limited(user_id, "link", limit=3, period=10):
        await message.reply("Please wait a moment before trying again.")
        return

    if not command.args:
        await message.reply("⚠️ Please provide your LeetCode username:\nExample: `/link username`", parse_mode="HTML")
        return

    leetcode_username = command.args.strip()
    
    # Generate verification code
    code = f"LC-{random.randint(1000, 9999)}"
    
    # Check if LeetCode user exists
    profile = await leetcode_client.get_user_profile(leetcode_username)
    if not profile:
        await message.reply(f"❌ Could not find a LeetCode user with username: {html.code(leetcode_username)}.\nMake sure you typed it correctly.", parse_mode="HTML")
        return

    # Link in database (unverified)
    await db.link_leetcode_account(user_id, leetcode_username, code)

    instructions = (
        f"🔗 {html.bold('Linking Request Received!')}\n\n"
        f"LeetCode Account: {html.bold(leetcode_username)}\n"
        f"Verification Code: {html.code(code)}\n\n"
        f"👉 To complete verification, please update your LeetCode profile biography/About Me section to contain your verification code: {html.code(code)}\n\n"
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
        await message.reply("⚠️ You haven't requested to link an account yet. Run `/link <username>` first.")
        return

    if link["verified"]:
        await message.reply("✅ Your LeetCode account is already verified and linked!")
        return

    leetcode_username = link["leetcode_username"]
    expected_code = link["verification_code"]

    await message.reply("🔍 Verifying your bio details... Please wait.")

    profile = await leetcode_client.get_user_profile(leetcode_username)
    if not profile or not profile.get("profile"):
        await message.reply("❌ Error fetching LeetCode profile. Please try again later.")
        return

    bio = profile["profile"].get("aboutMe") or ""
    if expected_code in bio:
        # Success! Mark as verified
        await db.verify_leetcode_account(user_id)
        # Reward user with some starting XP & Coins
        await db.add_xp_coins(user_id, xp=50, coins=50)
        
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
            parse_mode="HTML"
        )

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    user_id = message.from_user.id
    
    user_db = await db.get_user(user_id)
    if not user_db:
        # Create user record
        user_db = await db.create_user(user_id, message.from_user.username, message.from_user.first_name)

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
                
                solved_counts = {item["difficulty"]: item["count"] for item in submit_stats}
                solved_str = (
                    f"🟢 Easy: {solved_counts.get('Easy', 0)}\n"
                    f"🟡 Medium: {solved_counts.get('Medium', 0)}\n"
                    f"🔴 Hard: {solved_counts.get('Hard', 0)}\n"
                    f"🏆 Total Solved: {solved_counts.get('All', 0)}"
                )
            
            # Fetch ranking rating if possible
            ranking_info = await leetcode_client.get_user_contest_ranking(leetcode_username)
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
        leetcode_stats_str = f"\n\n⚠️ {html.bold('LeetCode Account')} not linked or verified.\nUse `/link <username>` to connect."

    profile_text = (
        f"👤 {html.bold('User Profile')}:\n"
        f"• Telegram ID: {html.code(user_id)}\n"
        f"• Level: {html.bold(user_db.get('level', 1))}\n"
        f"• XP: {html.bold(user_db.get('xp', 0))}\n"
        f"• Coins: {html.bold(user_db.get('coins', 0))}"
        f"{leetcode_stats_str}"
    )
    
    await message.reply(profile_text, parse_mode="HTML")
