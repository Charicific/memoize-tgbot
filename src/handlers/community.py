import logging
import datetime
import random
import asyncio
from typing import Optional
from aiogram import Router, F, html
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from src.utils.roles import RoleFilter, UserRole, get_user_role
from src.services.supabase_db import db
from src.services.leetcode import LeetCodeClient
from src.services.redis_cache import cache_manager

router = Router()
logger = logging.getLogger(__name__)

leetcode_client = LeetCodeClient()
VERIFY_COOLDOWNS = {}

@router.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message):
    user_id = message.from_user.id
    if await cache_manager.is_rate_limited(user_id, "leaderboard", limit=5, period=10):
        await message.reply("Slow down. Caching leaderboard...")
        return

    chat_type = message.chat.type
    if chat_type == "private":
        # Global leaderboard
        cache_key = "global_leaderboard"
        cached = await cache_manager.get(cache_key)
        if cached:
            await message.reply(cached, parse_mode="HTML")
            return

        users = await db.get_global_leaderboard(limit=10)
        if not users:
            await message.reply("🏆 No users on the global leaderboard yet. Solve problems to get listed!")
            return

        response = f"🏆 {html.bold('LeetCode Companion Global Leaderboard')} 🏆\n\n"
        for rank, u in enumerate(users, start=1):
            name = u['first_name'] or u['username'] or f"User {u['telegram_id']}"
            username_str = f" (@{u['username']})" if u['username'] else ""
            medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"
            response += f"{medal} {html.bold(name)}{username_str}\n   ✨ Level {u['level']} • {u['xp']} XP • {u['coins']} coins\n\n"

        await cache_manager.set(cache_key, response, expire_seconds=300)
        await message.reply(response, parse_mode="HTML")
    else:
        # Group leaderboard
        group_id = message.chat.id
        group_title = message.chat.title or "this Group"
        cache_key = f"group_leaderboard:{group_id}"
        cached = await cache_manager.get(cache_key)
        if cached:
            await message.reply(cached, parse_mode="HTML")
            return

        users = await db.get_group_leaderboard(group_id, limit=10)
        if not users:
            await message.reply("🏆 No active users on this group's leaderboard yet. Send messages or compete to get listed!")
            return

        response = f"🏆 {html.bold(f'{group_title} Leaderboard')} 🏆\n\n"
        for rank, u in enumerate(users, start=1):
            name = u['first_name'] or u['username'] or f"User {u['telegram_id']}"
            username_str = f" (@{u['username']})" if u['username'] else ""
            medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"
            response += f"{medal} {html.bold(name)}{username_str}\n   ✨ Level {u['level']} • {u['xp']} XP • {u['coins']} coins\n\n"

        await cache_manager.set(cache_key, response, expire_seconds=300)
        await message.reply(response, parse_mode="HTML")


@router.message(Command("gleaderboard"))
async def cmd_gleaderboard(message: Message):
    user_id = message.from_user.id
    if await cache_manager.is_rate_limited(user_id, "gleaderboard", limit=5, period=10):
        await message.reply("Slow down. Caching leaderboard...")
        return

    # Always show global leaderboard
    cache_key = "global_leaderboard"
    cached = await cache_manager.get(cache_key)
    if cached:
        await message.reply(cached, parse_mode="HTML")
        return

    users = await db.get_global_leaderboard(limit=10)
    if not users:
        await message.reply("🏆 No users on the global leaderboard yet. Solve problems to get listed!")
        return

    response = f"🏆 {html.bold('LeetCode Companion Global Leaderboard')} 🏆\n\n"
    for rank, u in enumerate(users, start=1):
        name = u['first_name'] or u['username'] or f"User {u['telegram_id']}"
        username_str = f" (@{u['username']})" if u['username'] else ""
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"
        response += f"{medal} {html.bold(name)}{username_str}\n   ✨ Level {u['level']} • {u['xp']} XP • {u['coins']} coins\n\n"

    await cache_manager.set(cache_key, response, expire_seconds=300)
    await message.reply(response, parse_mode="HTML")



OFFICIAL_LEETCODE_SLUGS = {
    "array", "string", "hash-table", "dynamic-programming", "math", "sorting",
    "greedy", "depth-first-search", "database", "breadth-first-search",
    "binary-search", "tree", "matrix", "binary-tree", "two-pointers",
    "bit-manipulation", "stack", "design", "heap-priority-queue", "backtracking",
    "graph", "simulation", "prefix-sum", "sliding-window", "trie",
    "linked-list", "recursion", "ordered-set", "monotonic-stack",
    "divide-and-conquer", "binary-search-tree", "queue", "union-find",
    "geometry", "combinatorics", "game-theory", "memoization", "topological-sort",
    "segment-tree", "interactive", "binary-indexed-tree", "hash-function",
    "string-matching", "rolling-hash", "shortest-path", "number-theory",
    "randomized", "monotonic-queue", "merge-sort", "iterator", "concurrency",
    "quickselect", "doubly-linked-list", "bucket-sort", "radix-sort",
    "counting-sort", "eulerian-circuit", "strongly-connected-component",
    "biconnected-component", "minimum-spanning-tree", "suffix-array",
    "line-sweep", "shell"
}

TAG_SYNONYMS = {
    "dp": "dynamic-programming",
    "dfs": "depth-first-search",
    "bfs": "breadth-first-search",
    "trees": "tree",
    "graphs": "graph",
    "arrays": "array",
    "strings": "string",
    "linkedlist": "linked-list",
    "twopointers": "two-pointers",
    "slidingwindow": "sliding-window",
    "binarysearch": "binary-search",
    "binarytree": "binary-tree",
    "bitmanipulation": "bit-manipulation",
    "priorityqueue": "heap-priority-queue",
    "priority-queue": "heap-priority-queue",
    "heap": "heap-priority-queue",
    "bst": "binary-search-tree",
    "bit": "binary-indexed-tree",
    "unionfind": "union-find",
    "toposort": "topological-sort",
    "mst": "minimum-spanning-tree",
    "scc": "strongly-connected-component",
}


def resolve_tag_slug(tag_str: str) -> Optional[str]:
    cleaned = tag_str.strip().lower()
    if not cleaned:
        return None
        
    if cleaned in TAG_SYNONYMS:
        return TAG_SYNONYMS[cleaned]
        
    normalized = cleaned.replace(" ", "-").replace("_", "-")
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
        
    if normalized in OFFICIAL_LEETCODE_SLUGS:
        return normalized
        
    import difflib
    matches = difflib.get_close_matches(normalized, list(OFFICIAL_LEETCODE_SLUGS), n=1, cutoff=0.8)
    if matches:
        return matches[0]
        
    best_match = None
    best_ratio = 0.0
    for slug in OFFICIAL_LEETCODE_SLUGS:
        raw_slug = slug.replace("-", "")
        raw_norm = normalized.replace("-", "")
        ratio = difflib.SequenceMatcher(None, raw_norm, raw_slug).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = slug
            
    if best_ratio >= 0.8:
        return best_match
        
    return normalized


def parse_battle_args(args_list):
    difficulty = None
    tags = []
    for arg in args_list:
        arg_lower = arg.lower()
        if arg_lower in ["easy", "medium", "hard"]:
            difficulty = arg_lower
        else:
            tags.append(arg_lower)
    tag_slug = None
    if tags:
        tag_str = " ".join(tags)
        tag_slug = resolve_tag_slug(tag_str)
    return difficulty, tag_slug


def is_traditional_random_battle(args_list: list) -> bool:
    if not args_list:
        return True
        
    difficulty, tag_slug = parse_battle_args(args_list)
    has_tag_args = any(arg.lower() not in ["easy", "medium", "hard"] for arg in args_list)
    
    if has_tag_args:
        if tag_slug in OFFICIAL_LEETCODE_SLUGS:
            return True
        return False
    else:
        return True



async def check_invitation_timeout(bot, battle_id):
    await asyncio.sleep(300)
    battle = await db.get_battle(battle_id)
    if not battle or battle["status"] != "PENDING":
        return
    await db.update_battle_status(battle_id, "CANCELLED")
    chat_id = battle.get("chat_id")
    msg_id = battle.get("message_id")
    if chat_id and msg_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception as e:
            logger.debug(f"Failed to delete expired battle message {msg_id} in {chat_id}: {e}")
        try:
            c_row = await db.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", battle["challenger_id"])
            o_row = await db.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", battle["opponent_id"])
            c_name = c_row["first_name"] or c_row["username"] or "Challenger"
            o_name = o_row["first_name"] or o_row["username"] or "Opponent"
            await bot.send_message(
                chat_id=chat_id,
                text=f"⏳ The LeetCode Battle Challenge from {html.bold(c_name)} to {html.bold(o_name)} has expired after 5 minutes of inactivity.",
                parse_mode="HTML"
            )
            
            # If it was a private DM challenge (chat_id == opponent_id), notify the challenger in DM too
            if chat_id == battle["opponent_id"]:
                try:
                    await bot.send_message(
                        chat_id=battle["challenger_id"],
                        text=f"⏳ Your LeetCode Battle Challenge to {html.bold(o_name)} has expired after 5 minutes of inactivity.",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to send expiration message to {chat_id}: {e}")


async def cancel_other_pending_challenges(bot, player_id, active_battle_id):
    rows = await db.fetch(
        "SELECT id, chat_id, message_id, challenger_id, opponent_id FROM battles WHERE (challenger_id = $1 OR opponent_id = $1) AND status = 'PENDING' AND id != $2::uuid",
        player_id, active_battle_id
    )
    for r in rows:
        other_id = r["id"]
        chat_id = r["chat_id"]
        msg_id = r["message_id"]
        await db.update_battle_status(str(other_id), "CANCELLED")
        if chat_id and msg_id:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception as e:
                logger.debug(f"Failed to delete cancelled battle message {msg_id} in {chat_id}: {e}")
            try:
                c_row = await db.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", r["challenger_id"])
                o_row = await db.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", r["opponent_id"])
                c_name = c_row["first_name"] or c_row["username"] or "Challenger"
                o_name = o_row["first_name"] or o_row["username"] or "Opponent"
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ LeetCode Battle Challenge between {html.bold(c_name)} and {html.bold(o_name)} was cancelled because one of the players started another battle.",
                    parse_mode="HTML"
                )
                
                # If it was a private DM challenge (chat_id == opponent_id), notify the challenger too
                if chat_id == r["opponent_id"]:
                    try:
                        await bot.send_message(
                            chat_id=r["challenger_id"],
                            text=f"⚠️ Your LeetCode Battle Challenge to {html.bold(o_name)} was cancelled because one of you started another battle.",
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"Failed to send cancellation notice to {chat_id}: {e}")


async def get_battle_from_message_or_args(message, command):
    if message.reply_to_message:
        replied_msg = message.reply_to_message
        # 1. Check 1v1 battles
        battle = await db.fetchrow(
            "SELECT * FROM battles WHERE chat_id = $1 AND message_id = $2",
            message.chat.id, replied_msg.message_id
        )
        if battle:
            return dict(battle)
        # 2. Check group battles
        gbattle = await db.fetchrow(
            "SELECT * FROM group_battles WHERE group_id = $1 AND message_id = $2",
            message.chat.id, replied_msg.message_id
        )
        if gbattle:
            return dict(gbattle)
            
        text = replied_msg.text or replied_msg.caption or ""
        import re
        uuid_pattern = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
        match = re.search(uuid_pattern, text)
        if match:
            battle_uuid = match.group(0)
            try:
                battle = await db.get_battle(battle_uuid)
                if battle:
                    return battle
                gbattle = await db.get_group_battle(battle_uuid)
                if gbattle:
                    return gbattle
            except Exception:
                pass
    if command.args:
        battle_uuid = command.args.strip()
        try:
            battle = await db.get_battle(battle_uuid)
            if battle:
                return battle
            gbattle = await db.get_group_battle(battle_uuid)
            if gbattle:
                return gbattle
        except Exception:
            pass
    return None


@router.message(Command("battle"))
async def cmd_battle(message: Message, command: CommandObject):
    user_id = message.from_user.id
    if await cache_manager.is_rate_limited(user_id, "battle", limit=3, period=15):
        await message.reply("Please wait a bit before challenging someone else.")
        return
    chat_type = message.chat.type
    if chat_type in ["group", "supergroup"]:
        is_disabled = await db.get_group_setting(message.chat.id, "battles")
        if is_disabled == "disable":
            await message.reply("⚠️ LeetCode battles are disabled in this group.")
            return
        if await db.is_group_battle_muted(message.chat.id, user_id):
            await message.reply("❌ You are muted from starting battles in this group.")
            return
    challenger_link = await db.get_linked_account(user_id)
    if not challenger_link or not challenger_link["verified"]:
        await message.reply(f"⚠️ You must link and verify your own LeetCode account first using {html.code('/link &lt;username&gt;')}!", parse_mode="HTML")
        return

    # Check if this is an open battle challenge in a group
    is_open_battle = False
    args_list = []
    if chat_type in ["group", "supergroup"] and command.args:
        args_split = command.args.split()
        if args_split[0].lower() == "open":
            is_open_battle = True
            args_list = args_split[1:]

    if is_open_battle:
        if is_traditional_random_battle(args_list):
            difficulty, tag_slug = parse_battle_args(args_list)
            if not difficulty:
                difficulty = random.choice(["easy", "medium", "hard"])
            difficulty_str = difficulty.capitalize()
            filter_info = difficulty_str
            if tag_slug:
                filter_info += f" with tag: {tag_slug}"
                
            progress_msg = await message.reply(f"🎲 Selecting a random {filter_info} problem... Please wait.")
            problems = await leetcode_client.get_problemset_questions(limit=100, difficulty=difficulty, tag_slug=tag_slug)
            free_problems = [p for p in problems if not p.get("isPaidOnly")]
            if not free_problems and tag_slug:
                await progress_msg.edit_text(
                    f"⚠️ Could not find any free problems with tag {html.code(tag_slug)} ({difficulty_str}).\n"
                    f"Selecting a random {difficulty_str} problem instead.",
                    parse_mode="HTML"
                )
                problems = await leetcode_client.get_problemset_questions(limit=100, difficulty=difficulty)
                free_problems = [p for p in problems if not p.get("isPaidOnly")]
                tag_slug = None
            if not free_problems:
                await progress_msg.edit_text("❌ Error picking a battle problem. Please try again.")
                return
                
            selected_prob = random.choice(free_problems)
            problem_slug = selected_prob["titleSlug"]
            problem_title = selected_prob["title"]
            
            expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
            
            battle = await db.create_group_battle(
                group_id=message.chat.id,
                problem_slug=problem_slug,
                problem_title=problem_title,
                difficulty=difficulty_str,
                created_by=user_id,
                expires_at=expires_at
            )
            battle_id = battle["id"]
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🎮 Join Battle", callback_data=f"gbattle_join:{battle_id}"),
                    InlineKeyboardButton(text="🏁 Start Battle", callback_data=f"gbattle_start:{battle_id}")
                ]
            ])
            
            creator_name = message.from_user.first_name or message.from_user.username or "Challenger"
            invitation_info = difficulty_str
            if tag_slug:
                invitation_info += f" (Tag: {tag_slug})"
                
            invite_msg = (
                f"⚔️ {html.bold('LeetCode Group Battle Arena Open!')} ⚔️\n\n"
                f"🆔 {html.bold('Battle ID:')} {html.code(str(battle_id))}\n"
                f"👤 Host: {html.bold(creator_name)}\n"
                f"🏆 Problem Category: {html.bold(invitation_info)}\n"
                f"⏳ Time Limit: {html.bold('60 minutes')} (once started)\n\n"
                f"👉 Click {html.bold('Join Battle')} below to enter the arena! "
                f"All registered group members can participate.\n"
                f"Host, click {html.bold('Start Battle')} once players have joined."
            )
            
            await progress_msg.delete()
            sent_msg = await message.bot.send_message(
                chat_id=message.chat.id,
                text=invite_msg,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await db.update_group_battle_message(str(battle_id), sent_msg.message_id)
            return
        else:
            # Specific problem query lobby
            query = " ".join(args_list)
            status_msg = await message.reply(f"🤖 Searching LeetCode for problem '{query}'...")
            matches = await leetcode_client.resolve_problem_query(query)
            if not matches:
                await status_msg.edit_text(f"❌ Could not find any problems matching '{query}'.")
                return

            if len(matches) == 1:
                selected_prob = matches[0]
                problem_slug = selected_prob["titleSlug"]
                problem_title = selected_prob["title"]
                difficulty_str = selected_prob["difficulty"].capitalize()
                expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
                
                battle = await db.create_group_battle(
                    group_id=message.chat.id,
                    problem_slug=problem_slug,
                    problem_title=problem_title,
                    difficulty=difficulty_str,
                    created_by=user_id,
                    expires_at=expires_at
                )
                battle_id = battle["id"]
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🎮 Join Battle", callback_data=f"gbattle_join:{battle_id}"),
                        InlineKeyboardButton(text="🏁 Start Battle", callback_data=f"gbattle_start:{battle_id}")
                    ]
                ])
                
                creator_name = message.from_user.first_name or message.from_user.username or "Challenger"
                q_num = selected_prob.get("frontendQuestionId", "")
                q_prefix = f"{q_num}. " if q_num else ""
                invite_msg = (
                    f"⚔️ {html.bold('LeetCode Group Battle Arena Open!')} ⚔️\n\n"
                    f"🆔 {html.bold('Battle ID:')} {html.code(str(battle_id))}\n"
                    f"👤 Host: {html.bold(creator_name)}\n"
                    f"🏆 Problem: {html.bold(f'{q_prefix}{problem_title} ({difficulty_str})')}\n"
                    f"⏳ Time Limit: {html.bold('60 minutes')} (once started)\n\n"
                    f"👉 Click {html.bold('Join Battle')} below to enter the arena! "
                    f"All registered group members can participate.\n"
                    f"Host, click {html.bold('Start Battle')} once players have joined."
                )
                
                await status_msg.delete()
                sent_msg = await message.bot.send_message(
                    chat_id=message.chat.id,
                    text=invite_msg,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                await db.update_group_battle_message(str(battle_id), sent_msg.message_id)
                return
            else:
                context = {
                    "type": "group",
                    "group_id": message.chat.id,
                    "problems": matches[:5]
                }
                await cache_manager.set(f"battle_search:{user_id}", context, expire_seconds=300)
                
                keyboard_buttons = []
                for idx, q in enumerate(matches[:5]):
                    button_text = f"⚔️ {q.get('frontendQuestionId', '')}. {q['title']} ({q.get('difficulty', 'Medium')})"
                    keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"gbattle_select_prob:{idx}")])
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
                await status_msg.edit_text(
                    f"🔍 Multiple matching problems found for '{query}'. Please select one to create the lobby:",
                    reply_markup=keyboard
                )
                return

    challenger_in_battle = await db.fetchrow(
        "SELECT id FROM battles WHERE (challenger_id = $1 OR opponent_id = $1) AND status IN ('ACTIVE', 'PAUSED')",
        user_id
    )
    if challenger_in_battle:
        await message.reply("❌ You cannot challenge anyone while you are already in an active or paused battle!")
        return
    opponent_username = None
    args_list = []
    if message.reply_to_message:
        opponent_user = message.reply_to_message.from_user
        if opponent_user.is_bot:
            await message.reply("🤖 You cannot challenge bots!")
            return
        opponent_id = opponent_user.id
        opponent_row = await db.get_user(opponent_id)
        if not opponent_row:
            opponent_name_str = opponent_user.first_name or opponent_user.username or "Opponent"
            await message.reply(
                f"❌ Could not find user {html.bold(opponent_name_str)} in our system.\n"
                f"Please make sure they have started the bot by clicking /start.",
                parse_mode="HTML"
            )
            return
        opponent_username = opponent_row["username"] or str(opponent_id)
        if command.args:
            args_list = command.args.split()
    else:
        if not command.args:
            await message.reply("⚠️ Please tag the friend you want to challenge or reply to their message:\nExample: `/battle @username` or reply to their message with `/battle`.", parse_mode="HTML")
            return
        args_all = command.args.split()
        first_arg = args_all[0]
        opponent_username = first_arg.replace("@", "")
        args_list = args_all[1:]
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
    if chat_type in ["group", "supergroup"]:
        if await db.is_group_battle_muted(message.chat.id, opponent_id):
            opponent_display = opponent_row['first_name'] or opponent_row['username'] or str(opponent_id)
            await message.reply(f"❌ Your opponent {html.bold(opponent_display)} is muted from participating in battles in this group.", parse_mode="HTML")
            return
    opponent_in_battle = await db.fetchrow(
        "SELECT id FROM battles WHERE (challenger_id = $1 OR opponent_id = $1) AND status IN ('ACTIVE', 'PAUSED')",
        opponent_id
    )
    if opponent_in_battle:
        opponent_display = opponent_row['first_name'] or opponent_row['username'] or str(opponent_id)
        await message.reply(f"❌ {html.bold(opponent_display)} is already in an active or paused battle!", parse_mode="HTML")
        return
    opponent_link = await db.get_linked_account(opponent_id)
    if not opponent_link or not opponent_link["verified"]:
        opponent_display = opponent_row['first_name'] or opponent_row['username'] or str(opponent_id)
        await message.reply(f"❌ Your opponent {html.bold(opponent_display)} has not linked their LeetCode profile yet.", parse_mode="HTML")
        return
    
    opp_display = opponent_row['first_name'] or opponent_row['username'] or str(opponent_id)
    opp_tag = f"@{opponent_row['username']}" if opponent_row['username'] else opp_display

    if is_traditional_random_battle(args_list):
        difficulty, tag_slug = parse_battle_args(args_list)
        if not difficulty:
            difficulty = random.choice(["easy", "medium", "hard"])
        difficulty_str = difficulty.capitalize()
        filter_info = difficulty_str
        if tag_slug:
            filter_info += f" with tag: {tag_slug}"
        progress_msg = await message.reply(f"🎲 Selecting a random {filter_info} problem... Please wait.")
        problems = await leetcode_client.get_problemset_questions(limit=100, difficulty=difficulty, tag_slug=tag_slug)
        free_problems = [p for p in problems if not p.get("isPaidOnly")]
        if not free_problems and tag_slug:
            await progress_msg.edit_text(
                f"⚠️ Could not find any free problems with tag {html.code(tag_slug)} ({difficulty_str}).\n"
                f"Selecting a random {difficulty_str} problem instead.",
                parse_mode="HTML"
            )
            problems = await leetcode_client.get_problemset_questions(limit=100, difficulty=difficulty)
            free_problems = [p for p in problems if not p.get("isPaidOnly")]
            tag_slug = None
        if not free_problems:
            await progress_msg.edit_text("❌ Error picking a battle problem. Please try again.")
            return
        try:
            await progress_msg.delete()
        except Exception:
            pass
        selected_prob = random.choice(free_problems)
        problem_slug = selected_prob["titleSlug"]
        problem_title = selected_prob["title"]
        expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        battle = await db.create_battle(user_id, opponent_id, problem_slug, problem_title, difficulty_str, expires_at)
        battle_id = battle["id"]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⚔️ Accept", callback_data=f"battle_accept:{battle_id}"),
                InlineKeyboardButton(text="🏳️ Decline", callback_data=f"battle_decline:{battle_id}")
            ]
        ])
        invitation_info = difficulty_str
        if tag_slug:
            invitation_info += f" (Tag: {tag_slug})"
        challenge_msg = (
            f"⚔️ {html.bold('LeetCode Battle Challenge!')} ⚔️\n\n"
            f"🆔 {html.bold('Battle ID:')} {html.code(str(battle_id))}\n"
            f"👤 Challenger: {html.bold(message.from_user.first_name or message.from_user.username)}\n"
            f"👤 Opponent: {html.bold(opp_display)}\n\n"
            f"🏆 Category: {html.bold(invitation_info)}\n"
            f"⏳ Time Limit: {html.bold('60 minutes')} once started\n\n"
            f"{opp_tag}, do you accept this challenge?"
        )
        is_private = message.chat.type == "private"
        
        if is_private:
            try:
                sent_msg = await message.bot.send_message(
                    chat_id=opponent_id,
                    text=challenge_msg,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                await db.update_battle_message(str(battle_id), sent_msg.chat.id, sent_msg.message_id)
                await message.reply(
                    f"⚔️ {html.bold('LeetCode Battle Challenge Sent!')} ⚔️\n\n"
                    f"🆔 {html.bold('Battle ID:')} {html.code(str(battle_id))}\n"
                    f"We have sent the challenge directly to <a href='tg://user?id={opponent_id}'>{opp_display}</a>'s DMs. "
                    f"Waiting for them to accept or decline.",
                    parse_mode="HTML"
                )
                try:
                    from src.utils.logging_helper import send_log
                    log_text = (
                        f"📩 {html.bold('LeetCode Battle Challenge Sent (DM)')} 📩\n\n"
                        f"• {html.bold('Battle ID:')} {html.code(str(battle_id))}\n"
                        f"• {html.bold('Challenger:')} <a href='tg://user?id={user_id}'>{message.from_user.first_name or message.from_user.username}</a> ({user_id})\n"
                        f"• {html.bold('Opponent:')} <a href='tg://user?id={opponent_id}'>{opp_display}</a> ({opponent_id})\n"
                        f"• {html.bold('Problem Category:')} {invitation_info}"
                    )
                    await send_log(log_text, disable_notification=True)
                except Exception as log_err:
                    logger.error(f"Error logging DM challenge: {log_err}")
            except Exception as dm_err:
                logger.error(f"Failed to send DM challenge: {dm_err}")
                await db.update_battle_status(str(battle_id), "CANCELLED")
                await message.reply(
                    f"❌ Cannot challenge {html.bold(opp_display)} in DM because the bot cannot message them. "
                    f"Please ask them to start the bot first.",
                    parse_mode="HTML"
                )
                return
        else:
            sent_msg = await message.bot.send_message(
                chat_id=message.chat.id,
                text=challenge_msg,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await db.update_battle_message(str(battle_id), sent_msg.chat.id, sent_msg.message_id)
            try:
                group_title = f" '{message.chat.title}'" if message.chat.title else ""
                await message.bot.send_message(
                    chat_id=opponent_id,
                    text=f"⚔️ You have been challenged to a LeetCode Battle by @{message.from_user.username or message.from_user.first_name} in group{group_title}! Check the group to accept or decline."
                )
            except Exception:
                pass
        asyncio.create_task(check_invitation_timeout(message.bot, str(battle_id)))
        return
    else:
        # Specific problem query 1v1 challenge
        query = " ".join(args_list)
        status_msg = await message.reply(f"🤖 Searching LeetCode for problem '{query}'...")
        matches = await leetcode_client.resolve_problem_query(query)
        if not matches:
            await status_msg.edit_text(f"❌ Could not find any problems matching '{query}'.")
            return

        if len(matches) == 1:
            selected_prob = matches[0]
            problem_slug = selected_prob["titleSlug"]
            problem_title = selected_prob["title"]
            difficulty_str = selected_prob["difficulty"].capitalize()
            expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
            battle = await db.create_battle(user_id, opponent_id, problem_slug, problem_title, difficulty_str, expires_at)
            battle_id = battle["id"]
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="⚔️ Accept", callback_data=f"battle_accept:{battle_id}"),
                    InlineKeyboardButton(text="🏳️ Decline", callback_data=f"battle_decline:{battle_id}")
                ]
            ])
            q_num = selected_prob.get("frontendQuestionId", "")
            q_prefix = f"{q_num}. " if q_num else ""
            challenge_msg = (
                f"⚔️ {html.bold('LeetCode Battle Challenge!')} ⚔️\n\n"
                f"🆔 {html.bold('Battle ID:')} {html.code(str(battle_id))}\n"
                f"👤 Challenger: {html.bold(message.from_user.first_name or message.from_user.username)}\n"
                f"👤 Opponent: {html.bold(opp_display)}\n\n"
                f"🏆 Problem: {html.bold(f'{q_prefix}{problem_title} ({difficulty_str})')}\n"
                f"⏳ Time Limit: {html.bold('60 minutes')} once started\n\n"
                f"{opp_tag}, do you accept this challenge?"
            )
            is_private = message.chat.type == "private"
            
            await status_msg.delete()
            if is_private:
                try:
                    sent_msg = await message.bot.send_message(
                        chat_id=opponent_id,
                        text=challenge_msg,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                    await db.update_battle_message(str(battle_id), sent_msg.chat.id, sent_msg.message_id)
                    await message.reply(
                        f"⚔️ {html.bold('LeetCode Battle Challenge Sent!')} ⚔️\n\n"
                        f"🆔 {html.bold('Battle ID:')} {html.code(str(battle_id))}\n"
                        f"We have sent the challenge directly to <a href='tg://user?id={opponent_id}'>{opp_display}</a>'s DMs. "
                        f"Waiting for them to accept or decline.",
                        parse_mode="HTML"
                    )
                    try:
                        from src.utils.logging_helper import send_log
                        log_text = (
                            f"📩 {html.bold('LeetCode Battle Challenge Sent (DM)')} 📩\n\n"
                            f"• {html.bold('Battle ID:')} {html.code(str(battle_id))}\n"
                            f"• {html.bold('Challenger:')} <a href='tg://user?id={user_id}'>{message.from_user.first_name or message.from_user.username}</a> ({user_id})\n"
                            f"• {html.bold('Opponent:')} <a href='tg://user?id={opponent_id}'>{opp_display}</a> ({opponent_id})\n"
                            f"• {html.bold('Problem:')} {selected_prob.get('frontendQuestionId', '')}. {problem_title} ({difficulty_str})"
                        )
                        await send_log(log_text, disable_notification=True)
                    except Exception as log_err:
                        logger.error(f"Error logging DM challenge: {log_err}")
                except Exception as dm_err:
                    logger.error(f"Failed to send DM challenge: {dm_err}")
                    await db.update_battle_status(str(battle_id), "CANCELLED")
                    await message.reply(
                        f"❌ Cannot challenge {html.bold(opp_display)} in DM because the bot cannot message them. "
                        f"Please ask them to start the bot first.",
                        parse_mode="HTML"
                    )
                    return
            else:
                sent_msg = await message.bot.send_message(
                    chat_id=message.chat.id,
                    text=challenge_msg,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                await db.update_battle_message(str(battle_id), sent_msg.chat.id, sent_msg.message_id)
                try:
                    group_title = f" '{message.chat.title}'" if message.chat.title else ""
                    await message.bot.send_message(
                        chat_id=opponent_id,
                        text=f"⚔️ You have been challenged to a LeetCode Battle by @{message.from_user.username or message.from_user.first_name} in group{group_title}! Check the group to accept or decline."
                    )
                except Exception:
                    pass
            asyncio.create_task(check_invitation_timeout(message.bot, str(battle_id)))
            return
        else:
            context = {
                "type": "1v1",
                "opponent_id": opponent_id,
                "opponent_display": opp_display,
                "opponent_username": opponent_row["username"] or str(opponent_id),
                "group_id": message.chat.id,
                "problems": matches[:5]
            }
            await cache_manager.set(f"battle_search:{user_id}", context, expire_seconds=300)
            
            keyboard_buttons = []
            for idx, q in enumerate(matches[:5]):
                button_text = f"⚔️ {q.get('frontendQuestionId', '')}. {q['title']} ({q.get('difficulty', 'Medium')})"
                keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"battle_select_prob:{idx}")])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            await status_msg.edit_text(
                f"🔍 Multiple matching problems found for '{query}'. Please select one to challenge {html.bold(opp_display)}:",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return


@router.callback_query(F.data.startswith("battle_select_prob:"))
async def process_battle_select_prob(callback_query: CallbackQuery):
    challenger_id = callback_query.from_user.id
    prob_idx = int(callback_query.data.split(":")[1])
    
    context = await cache_manager.get(f"battle_search:{challenger_id}")
    if not context or context.get("type") != "1v1":
        await callback_query.answer("⚠️ Either this menu has expired or only the challenger can click this.", show_alert=True)
        return
        
    problems = context.get("problems", [])
    if prob_idx >= len(problems):
        await callback_query.answer("⚠️ Selected problem is invalid.", show_alert=True)
        return
        
    selected_prob = problems[prob_idx]
    opponent_id = context["opponent_id"]
    opp_display = context["opponent_display"]
    opp_tag = f"@{context['opponent_username']}" if context["opponent_username"] and not context["opponent_username"].isdigit() else opp_display
    
    problem_slug = selected_prob["titleSlug"]
    problem_title = selected_prob["title"]
    difficulty_str = selected_prob["difficulty"].capitalize()
    
    await cache_manager.delete(f"battle_search:{challenger_id}")
    
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    battle = await db.create_battle(challenger_id, opponent_id, problem_slug, problem_title, difficulty_str, expires_at)
    battle_id = battle["id"]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚔️ Accept", callback_data=f"battle_accept:{battle_id}"),
            InlineKeyboardButton(text="🏳️ Decline", callback_data=f"battle_decline:{battle_id}")
        ]
    ])
    
    q_num = selected_prob.get("frontendQuestionId", "")
    q_prefix = f"{q_num}. " if q_num else ""
    challenge_msg = (
        f"⚔️ {html.bold('LeetCode Battle Challenge!')} ⚔️\n\n"
        f"🆔 {html.bold('Battle ID:')} {html.code(str(battle_id))}\n"
        f"👤 Challenger: {html.bold(callback_query.from_user.first_name or callback_query.from_user.username)}\n"
        f"👤 Opponent: {html.bold(opp_display)}\n\n"
        f"🏆 Problem: {html.bold(f'{q_prefix}{problem_title} ({difficulty_str})')}\n"
        f"⏳ Time Limit: {html.bold('60 minutes')} once started\n\n"
        f"{opp_tag}, do you accept this challenge?"
    )
    
    is_private = callback_query.message.chat.type == "private"
    
    if is_private:
        await callback_query.message.edit_text(
            f"⚔️ {html.bold('LeetCode Battle Challenge Sent!')} ⚔️\n\n"
            f"🆔 {html.bold('Battle ID:')} {html.code(str(battle_id))}\n"
            f"We have sent the challenge directly to <a href='tg://user?id={opponent_id}'>{opp_display}</a>'s DMs. "
            f"Waiting for them to accept or decline.",
            parse_mode="HTML"
        )
        
        try:
            sent_msg = await callback_query.bot.send_message(
                chat_id=opponent_id,
                text=challenge_msg,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await db.update_battle_message(str(battle_id), sent_msg.chat.id, sent_msg.message_id)
            
            try:
                from src.utils.logging_helper import send_log
                log_text = (
                    f"📩 {html.bold('LeetCode Battle Challenge Sent (DM)')} 📩\n\n"
                    f"• {html.bold('Battle ID:')} {html.code(str(battle_id))}\n"
                    f"• {html.bold('Challenger:')} <a href='tg://user?id={challenger_id}'>{callback_query.from_user.first_name or callback_query.from_user.username}</a> ({challenger_id})\n"
                    f"• {html.bold('Opponent:')} <a href='tg://user?id={opponent_id}'>{opp_display}</a> ({opponent_id})\n"
                    f"• {html.bold('Problem:')} {selected_prob.get('frontendQuestionId', '')}. {problem_title} ({difficulty_str})"
                )
                await send_log(log_text, disable_notification=True)
            except Exception as log_err:
                logger.error(f"Error logging DM challenge: {log_err}")
        except Exception as dm_err:
            logger.error(f"Failed to send DM challenge: {dm_err}")
            await db.update_battle_status(str(battle_id), "CANCELLED")
            await callback_query.message.reply(
                f"❌ Cannot challenge {html.bold(opp_display)} in DM because the bot cannot message them. "
                f"Please ask them to start the bot first.",
                parse_mode="HTML"
            )
    else:
        await callback_query.message.edit_text(
            text=challenge_msg,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await db.update_battle_message(str(battle_id), callback_query.message.chat.id, callback_query.message.message_id)
        
        try:
            group_title = f" '{callback_query.message.chat.title}'" if callback_query.message.chat.title else ""
            await callback_query.bot.send_message(
                chat_id=opponent_id,
                text=f"⚔️ You have been challenged to a LeetCode Battle by @{callback_query.from_user.username or callback_query.from_user.first_name} in group{group_title}! Check the group to accept or decline."
            )
        except Exception:
            pass
            
    asyncio.create_task(check_invitation_timeout(callback_query.bot, str(battle_id)))
    await callback_query.answer()


@router.callback_query(F.data.startswith("gbattle_select_prob:"))
async def process_gbattle_select_prob(callback_query: CallbackQuery):
    challenger_id = callback_query.from_user.id
    prob_idx = int(callback_query.data.split(":")[1])
    
    context = await cache_manager.get(f"battle_search:{challenger_id}")
    if not context or context.get("type") != "group":
        await callback_query.answer("⚠️ Either this menu has expired or only the host can click this.", show_alert=True)
        return
        
    problems = context.get("problems", [])
    if prob_idx >= len(problems):
        await callback_query.answer("⚠️ Selected problem is invalid.", show_alert=True)
        return
        
    selected_prob = problems[prob_idx]
    problem_slug = selected_prob["titleSlug"]
    problem_title = selected_prob["title"]
    difficulty_str = selected_prob["difficulty"].capitalize()
    
    await cache_manager.delete(f"battle_search:{challenger_id}")
    
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    battle = await db.create_group_battle(
        group_id=callback_query.message.chat.id,
        problem_slug=problem_slug,
        problem_title=problem_title,
        difficulty=difficulty_str,
        created_by=challenger_id,
        expires_at=expires_at
    )
    battle_id = battle["id"]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="... Join Battle", callback_data=f"gbattle_join:{battle_id}"),
            InlineKeyboardButton(text="🏁 Start Battle", callback_data=f"gbattle_start:{battle_id}")
        ]
    ])
    
    # Wait, the join button text was "🎮 Join Battle" in original. Let's make sure it is exactly correct.
    keyboard.inline_keyboard[0][0].text = "🎮 Join Battle"
    
    creator_name = callback_query.from_user.first_name or callback_query.from_user.username or "Challenger"
    q_num = selected_prob.get("frontendQuestionId", "")
    q_prefix = f"{q_num}. " if q_num else ""
    invite_msg = (
        f"⚔️ {html.bold('LeetCode Group Battle Arena Open!')} ⚔️\n\n"
        f"🆔 {html.bold('Battle ID:')} {html.code(str(battle_id))}\n"
        f"👤 Host: {html.bold(creator_name)}\n"
        f"🏆 Problem: {html.bold(f'{q_prefix}{problem_title} ({difficulty_str})')}\n"
        f"⏳ Time Limit: {html.bold('60 minutes')} (once started)\n\n"
        f"👉 Click {html.bold('Join Battle')} below to enter the arena! "
        f"All registered group members can participate.\n"
        f"Host, click {html.bold('Start Battle')} once players have joined."
    )
    
    await callback_query.message.edit_text(
        text=invite_msg,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await db.update_group_battle_message(str(battle_id), callback_query.message.message_id)
    await callback_query.answer()


@router.callback_query(F.data.startswith("battle_accept:"))
async def process_battle_accept(callback_query: CallbackQuery):
    battle_id = callback_query.data.split(":")[1]
    battle = await db.get_battle(battle_id)
    if not battle:
        await callback_query.answer("⚠️ Battle not found.", show_alert=True)
        return
    clicker_id = callback_query.from_user.id
    if clicker_id != battle["opponent_id"]:
        await callback_query.answer("⚠️ Only the challenged opponent can accept this battle.", show_alert=True)
        return
    if battle["status"] != "PENDING":
        await callback_query.answer(f"⚠️ This challenge is already {battle['status'].lower()}.", show_alert=True)
        return
    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = now + datetime.timedelta(hours=1)
    await db.update_battle_status(battle_id, "ACTIVE", started_at=now)
    await db.execute("UPDATE battles SET expires_at = $2 WHERE id = $1::uuid", battle_id, expires_at)
    asyncio.create_task(cancel_other_pending_challenges(callback_query.bot, battle["challenger_id"], battle_id))
    asyncio.create_task(cancel_other_pending_challenges(callback_query.bot, clicker_id, battle_id))
    from src.utils.logging_helper import send_log
    group_info = ""
    chat_id = battle.get("chat_id")
    if chat_id:
        if chat_id < 0:
            chat = callback_query.message.chat
            group_title = chat.title or "Group"
            group_username = chat.username
            msg_id = battle.get("message_id") or callback_query.message.message_id
            
            link = ""
            if msg_id:
                if group_username:
                    link = f"https://t.me/{group_username}/{msg_id}"
                elif str(chat.id).startswith("-100"):
                    link = f"https://t.me/c/{str(chat.id)[4:]}/{msg_id}"
                    
            if link:
                group_info = f"\n• {html.bold('Group:')} <a href='{link}'>{group_title}</a>"
            elif group_username:
                group_info = f"\n• {html.bold('Group:')} {group_title} (@{group_username})"
            else:
                group_info = f"\n• {html.bold('Group:')} {group_title} ({chat.id})"
        else:
            group_info = f"\n• {html.bold('Group:')} Private DM"

    log_text = (
        f"⚔️ {html.bold('LeetCode Battle Started')} ⚔️\n\n"
        f"• {html.bold('Battle ID:')} {html.code(str(battle_id))}\n"
        f"• {html.bold('Challenger:')} <a href='tg://user?id={battle['challenger_id']}'>Link</a> ({battle['challenger_id']})\n"
        f"• {html.bold('Opponent:')} @{callback_query.from_user.username or callback_query.from_user.first_name} ({callback_query.from_user.id})\n"
        f"• {html.bold('Problem:')} {battle['problem_title']}"
        f"{group_info}"
    )
    await send_log(log_text, disable_notification=True)
    battle_url = f"https://leetcode.com/problems/{battle['problem_slug']}"
    start_msg = (
        f"⚔️ {html.bold('Battle Started!')} ⚔️\n\n"
        f"🆔 {html.bold('Battle ID:')} {html.code(str(battle_id))}\n"
        f"🏆 Problem: <a href='{battle_url}'>{battle['problem_title']}</a> ({battle.get('difficulty', 'Medium') or 'Medium'})\n"
        f"⏱️ Deadline: {html.code('60 minutes')} from now\n\n"
        f"🚀 Solve the problem on LeetCode and submit it.\n"
        f"The first one to get a green accepted submission wins!\n\n"
        f"We will automatically poll LeetCode for results. Good luck!"
    )
    verify_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Verify Solve", callback_data=f"battle_verify:{battle_id}")]
    ])
    await callback_query.message.edit_text(start_msg, reply_markup=verify_keyboard, parse_mode="HTML", disable_web_page_preview=True)
    try:
        await callback_query.message.bot.send_message(
            chat_id=battle["challenger_id"],
            text=f"⚔️ Your challenge to @{callback_query.from_user.username or callback_query.from_user.first_name} was accepted!\n\n" + start_msg,
            reply_markup=verify_keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception:
        pass
    await callback_query.answer("Battle accepted!")


@router.callback_query(F.data.startswith("battle_decline:"))
async def process_battle_decline(callback_query: CallbackQuery):
    battle_id = callback_query.data.split(":")[1]
    battle = await db.get_battle(battle_id)
    if not battle:
        await callback_query.answer("⚠️ Battle not found.", show_alert=True)
        return
    if callback_query.from_user.id != battle["opponent_id"]:
        await callback_query.answer("⚠️ Only the challenged opponent can decline this challenge.", show_alert=True)
        return
    if battle["status"] != "PENDING":
        await callback_query.answer("⚠️ This challenge is no longer pending.", show_alert=True)
        return
    await db.update_battle_status(battle_id, "DECLINED")
    opponent_name = callback_query.from_user.first_name or callback_query.from_user.username or "Opponent"
    await callback_query.message.edit_text(f"❌ LeetCode Battle Challenge was declined by {html.bold(opponent_name)}.", parse_mode="HTML")
    try:
        opponent_name_full = callback_query.from_user.username or callback_query.from_user.first_name
        await callback_query.message.bot.send_message(
            chat_id=battle["challenger_id"],
            text=f"😔 Your battle challenge was declined by @{opponent_name_full}."
        )
    except Exception:
        pass
    await callback_query.answer("Battle declined.")


# --- Group settings and moderation commands ---

@router.message(Command("clear_group_history"), RoleFilter(UserRole.GROUP_OWNER))
async def cmd_clear_group_history(message: Message):
    """
    Clears leaderboard stats for the group. Restricted to Group Owner or higher.
    """
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("❌ This command can only be used in groups.")
        return

    await db.clear_group_history(message.chat.id)
    await message.reply("✅ Successfully reset all leaderboard stats for this group.")

@router.message(Command("mute_battle"), RoleFilter(UserRole.GROUP_OWNER))
async def cmd_mute_battle(message: Message, command: CommandObject):
    """
    Mutes or unmutes a member from starting/accepting battles in the group.
    Restricted to Group Owner or higher.
    Usage: /mute_battle <telegram_id_or_username> <on/off>
    """
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("❌ This command can only be used in groups.")
        return

    if not command.args or len(command.args.split()) != 2:
        await message.reply(f"⚠️ Usage: {html.code(html.quote('/mute_battle <telegram_id_or_username> <on/off>'))}", parse_mode="HTML")
        return

    identifier, toggle = command.args.split()
    toggle = toggle.lower()

    if toggle not in ["on", "off"]:
        await message.reply("❌ Invalid setting. Choose `on` (to mute) or `off` (to unmute).")
        return

    target_user = await db.get_user_by_id_or_username(identifier)
    if not target_user:
        await message.reply(f"❌ User <b>{html.quote(identifier)}</b> not found in database.", parse_mode="HTML")
        return

    target_id = target_user["telegram_id"]
    mute = (toggle == "on")

    # Group owner/admins cannot mute higher authority
    bot = message.bot
    target_role = await get_user_role(
        user_id=target_id,
        chat_id=message.chat.id,
        chat_type=message.chat.type,
        bot=bot
    )
    if target_role >= UserRole.COORDINATOR:
        await message.reply("❌ Cannot mute battles for global Coordinators or Super Admins.")
        return

    await db.mute_group_battle(message.chat.id, target_id, mute)

    status_str = "muted from participating in" if mute else "unmuted for"
    await message.reply(
        f"✅ User {html.bold(target_user['first_name'] or target_user['username'] or str(target_id))} is now {status_str} battles in this group.",
        parse_mode="HTML"
    )

@router.message(Command("config_group"), RoleFilter(UserRole.GROUP_ADMIN))
async def cmd_config_group(message: Message, command: CommandObject):
    """
    Configure group-specific features:
    - battles [enable/disable]
    - feed [enable/disable]
    Usage: /config_group <setting> <value>
    """
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("❌ This command can only be used in groups.")
        return

    if not command.args or len(command.args.split()) != 2:
        await message.reply(
            f"⚠️ Usage: {html.code(html.quote('/config_group <setting> <value>'))}\n"
            f"Supported configurations:\n"
            f"• {html.code(html.quote('/config_group battles enable/disable'))}\n"
            f"• {html.code(html.quote('/config_group feed enable/disable'))}",
            parse_mode="HTML"
        )
        return

    setting, value = command.args.split()
    setting = setting.lower()
    value = value.lower()

    if setting not in ["battles", "feed"]:
        await message.reply("❌ Invalid setting. Choose `battles` or `feed`.")
        return

    if value not in ["enable", "disable"]:
        await message.reply("❌ Invalid value. Choose `enable` or `disable`.")
        return

    await db.set_group_setting(message.chat.id, setting, value)
    
    # Send confirmation
    status_str = "enabled" if value == "enable" else "disabled"
    await message.reply(f"✅ Group feature {html.bold(setting)} has been {html.bold(status_str)}.", parse_mode="HTML")


# --- Interactive Battle Controls ---

@router.message(Command("stopbattle"))
async def cmd_stopbattle(message: Message, command: CommandObject):
    user_id = message.from_user.id
    battle = await get_battle_from_message_or_args(message, command)
    if not battle:
        rows = await db.fetch(
            "SELECT * FROM battles WHERE (challenger_id = $1 OR opponent_id = $1) AND status IN ('ACTIVE', 'PAUSED')",
            user_id
        )
        group_rows = await db.fetch(
            """
            SELECT DISTINCT gb.*
            FROM group_battles gb
            LEFT JOIN group_battle_participants gbp ON gb.id = gbp.group_battle_id
            WHERE (gbp.telegram_id = $1 OR gb.created_by = $1) AND gb.status IN ('ACTIVE', 'PAUSED')
            """,
            user_id
        )
        all_battles = [dict(r) for r in rows] + [dict(r) for r in group_rows]
        if len(all_battles) > 1:
            await message.reply("⚠️ You have multiple active/paused battles. Please specify the battle ID or reply to the battle message:\n`/stopbattle <battle_uuid>`")
            return
        elif len(all_battles) == 1:
            battle = all_battles[0]
        else:
            await message.reply("❌ You do not have any active or paused battles.")
            return

    battle_id = str(battle["id"])
    is_group = "group_id" in battle

    if is_group:
        role = await get_user_role(user_id, message.chat.id, message.chat.type, message.bot)
        has_admin_override = (role >= UserRole.GROUP_ADMIN) or (role >= UserRole.COORDINATOR)
        is_host = (user_id == battle["created_by"])
        if not is_host and not has_admin_override:
            await message.reply("❌ You do not have permission to stop this battle.")
            return
        
        await db.update_group_battle_status(battle_id, "CANCELLED")
        
        # Log group battle cancelled to log channel
        try:
            from src.utils.logging_helper import send_log
            chat = message.chat
            group_title = chat.title or "Group"
            group_username = chat.username
            msg_id = battle.get("message_id")
            
            link = ""
            if msg_id:
                if group_username:
                    link = f"https://t.me/{group_username}/{msg_id}"
                elif str(chat.id).startswith("-100"):
                    link = f"https://t.me/c/{str(chat.id)[4:]}/{msg_id}"
                    
            if link:
                group_info = f"<a href='{link}'>{group_title}</a>"
            elif group_username:
                group_info = f"{group_title} (@{group_username})"
            else:
                group_info = f"{group_title} ({chat.id})"
                
            log_text = (
                f"⏹️ {html.bold('Group LeetCode Battle Cancelled')} ⏹️\n\n"
                f"• {html.bold('Battle ID:')} {html.code(battle_id)}\n"
                f"• {html.bold('Group:')} {group_info}\n"
                f"• {html.bold('Problem:')} {battle['problem_title']}\n"
                f"• {html.bold('Cancelled by:')} @{message.from_user.username or message.from_user.first_name} ({message.from_user.id})"
            )
            await send_log(log_text, disable_notification=True)
        except Exception as log_err:
            logger.error(f"Error logging group battle cancellation: {log_err}")
        await message.reply(
            f"⏹️ {html.bold('Group Battle Cancelled')} ⏹️\n\n"
            f"🆔 Battle ID: {html.code(battle_id)}\n"
            f"Problem: {battle['problem_title']}\n\n"
            f"This group battle has been stopped. No points/XP awarded.",
            parse_mode="HTML"
        )
        return

    is_player = (user_id == battle["challenger_id"] or user_id == battle["opponent_id"])
    role = await get_user_role(user_id, message.chat.id, message.chat.type, message.bot)
    has_admin_override = (role >= UserRole.GROUP_ADMIN) or (role >= UserRole.COORDINATOR)
    if not is_player and not has_admin_override:
        await message.reply("❌ You do not have permission to stop this battle.")
        return

    if has_admin_override and not is_player:
        await db.update_battle_status(battle_id, "CANCELLED", ended_at=datetime.datetime.now(datetime.timezone.utc))
        group_info = ""
        chat_id = battle.get("chat_id")
        if chat_id:
            if chat_id < 0:
                chat = message.chat
                group_title = chat.title or "Group"
                group_username = chat.username
                msg_id = battle.get("message_id")
                link = ""
                if msg_id:
                    if group_username:
                        link = f"https://t.me/{group_username}/{msg_id}"
                    elif str(chat_id).startswith("-100"):
                        link = f"https://t.me/c/{str(chat_id)[4:]}/{msg_id}"
                        
                if link:
                    group_info = f"\n• {html.bold('Group:')} <a href='{link}'>{group_title}</a>"
                elif group_username:
                    group_info = f"\n• {html.bold('Group:')} {group_title} (@{group_username})"
                else:
                    group_info = f"\n• {html.bold('Group:')} {group_title} ({chat_id})"
            else:
                group_info = f"\n• {html.bold('Group:')} Private DM"

        log_text = (
            f"⏹️ {html.bold('Battle Forcefully Cancelled by Admin')} ⏹️\n\n"
            f"• {html.bold('Battle ID:')} {html.code(battle_id)}\n"
            f"• {html.bold('Challenger:')} <a href='tg://user?id={battle['challenger_id']}'>Link</a> ({battle['challenger_id']})\n"
            f"• {html.bold('Opponent:')} <a href='tg://user?id={battle['opponent_id']}'>Link</a> ({battle['opponent_id']})\n"
            f"• {html.bold('Cancelled by:')} @{message.from_user.username or message.from_user.first_name} ({message.from_user.id})"
            f"{group_info}"
        )
        await log_admin_activity(log_text, message)
        await message.reply(
            f"⏹️ {html.bold('Battle Forcefully Cancelled')} ⏹️\n\n"
            f"🆔 Battle ID: {html.code(battle_id)}\n"
            f"👤 Challenger: <a href='tg://user?id={battle['challenger_id']}'>Link</a>\n"
            f"👤 Opponent: <a href='tg://user?id={battle['opponent_id']}'>Link</a>\n\n"
            f"An administrator ({message.from_user.first_name}) has cancelled this battle. No points/XP awarded.",
            parse_mode="HTML"
        )
        return

    opponent_id = battle["opponent_id"] if user_id == battle["challenger_id"] else battle["challenger_id"]
    initiator_row = await db.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", user_id)
    opponent_row = await db.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", opponent_id)
    initiator_name = initiator_row["first_name"] or initiator_row["username"] or "Challenger"
    opponent_name = opponent_row["first_name"] or opponent_row["username"] or "Opponent"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🤝 Accept Draw", callback_data=f"draw_accept:{battle_id}:{opponent_id}"),
            InlineKeyboardButton(text="❌ Decline Draw", callback_data=f"draw_decline:{battle_id}:{opponent_id}")
        ]
    ])

    await message.reply(
        f"🤝 {html.bold('Draw Offer Proposed!')} 🤝\n\n"
        f"🆔 {html.bold('Battle ID:')} {html.code(battle_id)}\n"
        f"Player {html.bold(initiator_name)} has proposed to end the battle in a draw.\n"
        f"Player {html.bold(opponent_name)}, do you agree?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("draw_accept:"))
async def process_draw_accept(callback_query: CallbackQuery):
    parts = callback_query.data.split(":")
    battle_id = parts[1]
    target_opponent_id = int(parts[2])
    clicker_id = callback_query.from_user.id
    if clicker_id != target_opponent_id:
        await callback_query.answer("⚠️ Only the challenged opponent can accept the draw offer.", show_alert=True)
        return
    battle = await db.get_battle(battle_id)
    if not battle:
        await callback_query.answer("❌ Battle not found.", show_alert=True)
        return
    if battle["status"] not in ["ACTIVE", "PAUSED"]:
        await callback_query.answer(f"⚠️ Battle is already {battle['status'].lower()}.", show_alert=True)
        return
    await db.update_battle_status(battle_id, "COMPLETED", ended_at=datetime.datetime.now(datetime.timezone.utc))
    from src.utils.logging_helper import send_log
    group_info = ""
    chat_id = battle.get("chat_id")
    if chat_id:
        if chat_id < 0:
            try:
                chat = callback_query.message.chat
                group_title = chat.title or "Group"
                group_username = chat.username
            except Exception:
                group_title = "Group"
                group_username = None
                
            msg_id = battle.get("message_id")
            link = ""
            if msg_id:
                if group_username:
                    link = f"https://t.me/{group_username}/{msg_id}"
                elif str(chat_id).startswith("-100"):
                    link = f"https://t.me/c/{str(chat_id)[4:]}/{msg_id}"
                    
            if link:
                group_info = f"\n• {html.bold('Group:')} <a href='{link}'>{group_title}</a>"
            elif group_username:
                group_info = f"\n• {html.bold('Group:')} {group_title} (@{group_username})"
            else:
                group_info = f"\n• {html.bold('Group:')} {group_title} ({chat_id})"
        else:
            group_info = f"\n• {html.bold('Group:')} Private DM"

    log_text = (
        f"🤝 {html.bold('LeetCode Battle Draw')} 🤝\n\n"
        f"• {html.bold('Battle ID:')} {html.code(battle_id)}\n"
        f"• {html.bold('Problem:')} {battle['problem_title']}\n"
        f"• {html.bold('Players:')} <a href='tg://user?id={battle['challenger_id']}'>Link</a> and <a href='tg://user?id={battle['opponent_id']}'>Link</a>\n"
        f"Both players agreed to end the battle in a draw."
        f"{group_info}"
    )
    await send_log(log_text, disable_notification=True)
    await callback_query.message.edit_text(
        f"🤝 {html.bold('LeetCode Battle Ended in a Draw!')} 🤝\n\n"
        f"🆔 {html.bold('Battle ID:')} {html.code(battle_id)}\n"
        f"Both players agreed to end the battle in a draw. No XP or coins awarded.",
        parse_mode="HTML"
    )
    await callback_query.answer("Draw accepted!")


@router.callback_query(F.data.startswith("draw_decline:"))
async def process_draw_decline(callback_query: CallbackQuery):
    parts = callback_query.data.split(":")
    battle_id = parts[1]
    target_opponent_id = int(parts[2])
    clicker_id = callback_query.from_user.id
    if clicker_id != target_opponent_id:
        await callback_query.answer("⚠️ Only the challenged opponent can decline the draw offer.", show_alert=True)
        return
    battle = await db.get_battle(battle_id)
    if not battle:
        await callback_query.answer("❌ Battle not found.", show_alert=True)
        return
    if battle["status"] not in ["ACTIVE", "PAUSED"]:
        await callback_query.answer(f"⚠️ Battle is already {battle['status'].lower()}.", show_alert=True)
        return
    initiator_id = battle["challenger_id"] if clicker_id == battle["opponent_id"] else battle["opponent_id"]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏳️ Forfeit (Opponent Wins)", callback_data=f"draw_forfeit:{battle_id}:{initiator_id}"),
            InlineKeyboardButton(text="⚔️ Keep Playing", callback_data=f"draw_keep:{battle_id}:{initiator_id}")
        ]
    ])
    await callback_query.message.edit_text(
        f"❌ {html.bold('Draw Offer Declined!')}\n\n"
        f"🆔 {html.bold('Battle ID:')} {html.code(battle_id)}\n"
        f"Your opponent declined the draw offer. Initiator, do you want to forfeit or keep playing?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback_query.answer("Draw offer declined.")


@router.callback_query(F.data.startswith("draw_forfeit:"))
async def process_draw_forfeit(callback_query: CallbackQuery):
    parts = callback_query.data.split(":")
    battle_id = parts[1]
    target_initiator_id = int(parts[2])
    clicker_id = callback_query.from_user.id
    if clicker_id != target_initiator_id:
        await callback_query.answer("⚠️ Only the draw initiator can forfeit.", show_alert=True)
        return
    battle = await db.get_battle(battle_id)
    if not battle:
        await callback_query.answer("❌ Battle not found.", show_alert=True)
        return
    if battle["status"] not in ["ACTIVE", "PAUSED"]:
        await callback_query.answer(f"⚠️ Battle is already {battle['status'].lower()}.", show_alert=True)
        return
    winner_id = battle["opponent_id"] if clicker_id == battle["challenger_id"] else battle["challenger_id"]
    loser_id = clicker_id
    await db.update_battle_status(battle_id, "COMPLETED", winner_id=winner_id, ended_at=datetime.datetime.now(datetime.timezone.utc))
    await db.add_xp_coins(winner_id, xp=100, coins=20)
    await db.add_xp_coins(loser_id, xp=20, coins=0)
    winner_row = await db.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", winner_id)
    loser_row = await db.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", loser_id)
    w_name = winner_row["first_name"] or winner_row["username"] or "Opponent"
    l_name = loser_row["first_name"] or loser_row["username"] or "Challenger"
    from src.utils.logging_helper import send_log
    group_info = ""
    chat_id = battle.get("chat_id")
    if chat_id:
        if chat_id < 0:
            try:
                chat = callback_query.message.chat
                group_title = chat.title or "Group"
                group_username = chat.username
            except Exception:
                group_title = "Group"
                group_username = None
                
            msg_id = battle.get("message_id")
            link = ""
            if msg_id:
                if group_username:
                    link = f"https://t.me/{group_username}/{msg_id}"
                elif str(chat_id).startswith("-100"):
                    link = f"https://t.me/c/{str(chat_id)[4:]}/{msg_id}"
                    
            if link:
                group_info = f"\n• {html.bold('Group:')} <a href='{link}'>{group_title}</a>"
            elif group_username:
                group_info = f"\n• {html.bold('Group:')} {group_title} (@{group_username})"
            else:
                group_info = f"\n• {html.bold('Group:')} {group_title} ({chat_id})"
        else:
            group_info = f"\n• {html.bold('Group:')} Private DM"

    log_text = (
        f"🏳️ {html.bold('LeetCode Battle Forfeited')} 🏳️\n\n"
        f"• {html.bold('Battle ID:')} {html.code(battle_id)}\n"
        f"• {html.bold('Problem:')} {battle['problem_title']}\n"
        f"• {html.bold('Winner:')} {w_name} ({winner_id})\n"
        f"• {html.bold('Loser:')} {l_name} ({loser_id})"
        f"{group_info}"
    )
    await send_log(log_text, disable_notification=True)
    await callback_query.message.edit_text(
        f"🏳️ {html.bold('Battle Forfeited!')} 🏳️\n\n"
        f"🆔 {html.bold('Battle ID:')} {html.code(battle_id)}\n"
        f"Player {html.bold(l_name)} has forfeited the battle.\n"
        f"🥇 Winner: {html.bold(w_name)} (Awarded 100 XP, 20 coins)\n"
        f"🥈 Loser: {html.bold(l_name)} (Awarded 20 XP)",
        parse_mode="HTML"
    )
    await callback_query.answer("Battle forfeited.")


@router.callback_query(F.data.startswith("draw_keep:"))
async def process_draw_keep(callback_query: CallbackQuery):
    parts = callback_query.data.split(":")
    battle_id = parts[1]
    target_initiator_id = int(parts[2])
    clicker_id = callback_query.from_user.id
    if clicker_id != target_initiator_id:
        await callback_query.answer("⚠️ Only the draw initiator can select this option.", show_alert=True)
        return
    battle = await db.get_battle(battle_id)
    if not battle:
        await callback_query.answer("❌ Battle not found.", show_alert=True)
        return
    if battle["status"] not in ["ACTIVE", "PAUSED"]:
        await callback_query.answer(f"⚠️ Battle is already {battle['status'].lower()}.", show_alert=True)
        return
    await callback_query.message.edit_text(
        f"⚔️ {html.bold('Battle Continues!')} ⚔️\n\n"
        f"🆔 {html.bold('Battle ID:')} {html.code(battle_id)}\n"
        f"The battle for {html.bold(battle['problem_title'])} is active. Solve the problem on LeetCode!",
        parse_mode="HTML"
    )
    await callback_query.answer("Battle continues!")


@router.message(Command("pausebattle"))
async def cmd_pausebattle(message: Message, command: CommandObject):
    user_id = message.from_user.id
    battle = await get_battle_from_message_or_args(message, command)
    if not battle:
        rows = await db.fetch(
            "SELECT * FROM battles WHERE (challenger_id = $1 OR opponent_id = $1) AND status = 'ACTIVE'",
            user_id
        )
        group_rows = await db.fetch(
            """
            SELECT DISTINCT gb.*
            FROM group_battles gb
            LEFT JOIN group_battle_participants gbp ON gb.id = gbp.group_battle_id
            WHERE (gbp.telegram_id = $1 OR gb.created_by = $1) AND gb.status = 'ACTIVE'
            """,
            user_id
        )
        all_battles = [dict(r) for r in rows] + [dict(r) for r in group_rows]
        if len(all_battles) > 1:
            await message.reply("⚠️ You have multiple active battles. Please specify the battle ID or reply to the battle message:\n`/pausebattle <battle_uuid>`")
            return
        elif len(all_battles) == 1:
            battle = all_battles[0]
        else:
            await message.reply("❌ You do not have any active battles to pause.")
            return

    battle_id = str(battle["id"])
    is_group = "group_id" in battle
    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = battle["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    elif expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
    remaining = max(0, int((expires_at - now).total_seconds()))

    if is_group:
        role = await get_user_role(user_id, message.chat.id, message.chat.type, message.bot)
        has_admin_override = (role >= UserRole.GROUP_ADMIN) or (role >= UserRole.COORDINATOR)
        is_host = (user_id == battle["created_by"])
        if not is_host and not has_admin_override:
            await message.reply("❌ You do not have permission to pause this battle.")
            return
        if battle["status"] != "ACTIVE":
            await message.reply(f"❌ Battle is not active (Status: {battle['status']}).")
            return

        await db.execute(
            "UPDATE group_battles SET status = 'PAUSED', paused_at = $2, remaining_seconds = $3 WHERE id = $1::uuid",
            battle_id, now, remaining
        )
        await message.reply(
            f"⏸️ {html.bold('Group Battle Paused')} ⏸️\n\n"
            f"🆔 Battle ID: {html.code(battle_id)}\n"
            f"Problem: {battle['problem_title']}\n\n"
            f"The battle timer has been frozen at {remaining // 60}m {remaining % 60}s by the host or an administrator.",
            parse_mode="HTML"
        )
        return

    is_player = (user_id == battle["challenger_id"] or user_id == battle["opponent_id"])
    role = await get_user_role(user_id, message.chat.id, message.chat.type, message.bot)
    has_admin_override = (role >= UserRole.GROUP_ADMIN) or (role >= UserRole.COORDINATOR)
    if not is_player and not has_admin_override:
        await message.reply("❌ You do not have permission to pause this battle.")
        return
    if battle["status"] != "ACTIVE":
        await message.reply(f"❌ Battle is not active (Status: {battle['status']}).")
        return

    battle_id = str(battle["id"])
    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = battle["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    elif expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
    remaining = max(0, int((expires_at - now).total_seconds()))

    if has_admin_override and not is_player:
        await db.execute(
            "UPDATE battles SET status = 'PAUSED', paused_at = $2, remaining_seconds = $3 WHERE id = $1::uuid",
            battle_id, now, remaining
        )
        from src.utils.logging_helper import log_admin_activity
        log_text = (
            f"⏸️ {html.bold('Battle Forcefully Paused by Admin')} ⏸️\n\n"
            f"• {html.bold('Battle ID:')} {html.code(battle_id)}\n"
            f"• {html.bold('Problem:')} {battle['problem_title']}\n"
            f"• {html.bold('Paused by:')} @{message.from_user.username or message.from_user.first_name} ({message.from_user.id})"
        )
        await log_admin_activity(log_text, message)
        await message.reply(
            f"⏸️ {html.bold('Battle Forcefully Paused')} ⏸️\n\n"
            f"🆔 Battle ID: {html.code(battle_id)}\n"
            f"An administrator ({message.from_user.first_name}) has forcefully paused this battle.",
            parse_mode="HTML"
        )
        return

    opponent_id = battle["opponent_id"] if user_id == battle["challenger_id"] else battle["challenger_id"]
    initiator_row = await db.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", user_id)
    opponent_row = await db.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", opponent_id)
    initiator_name = initiator_row["first_name"] or initiator_row["username"] or "Challenger"
    opponent_name = opponent_row["first_name"] or opponent_row["username"] or "Opponent"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏸️ Accept Pause", callback_data=f"pause_accept:{battle_id}:{opponent_id}"),
            InlineKeyboardButton(text="❌ Decline Pause", callback_data=f"pause_decline:{battle_id}:{opponent_id}")
        ]
    ])
    await message.reply(
        f"⏸️ {html.bold('Pause Request!')} ⏸️\n\n"
        f"🆔 {html.bold('Battle ID:')} {html.code(battle_id)}\n"
        f"Player {html.bold(initiator_name)} wants to pause the battle (Remaining Time: {remaining // 60}m {remaining % 60}s).\n"
        f"Player {html.bold(opponent_name)}, do you agree?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("pause_accept:"))
async def process_pause_accept(callback_query: CallbackQuery):
    parts = callback_query.data.split(":")
    battle_id = parts[1]
    target_opponent_id = int(parts[2])
    clicker_id = callback_query.from_user.id
    if clicker_id != target_opponent_id:
        await callback_query.answer("⚠️ Only the challenged opponent can accept the pause offer.", show_alert=True)
        return
    battle = await db.get_battle(battle_id)
    if not battle:
        await callback_query.answer("❌ Battle not found.", show_alert=True)
        return
    if battle["status"] != "ACTIVE":
        await callback_query.answer(f"⚠️ Battle is already {battle['status'].lower()}.", show_alert=True)
        return
    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = battle["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    elif expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
    remaining = max(0, int((expires_at - now).total_seconds()))

    await db.execute(
        "UPDATE battles SET status = 'PAUSED', paused_at = $2, remaining_seconds = $3 WHERE id = $1::uuid",
        battle_id, now, remaining
    )
    from src.utils.logging_helper import send_log
    log_text = (
        f"⏸️ {html.bold('LeetCode Battle Paused')} ⏸️\n\n"
        f"• {html.bold('Battle ID:')} {html.code(battle_id)}\n"
        f"• {html.bold('Problem:')} {battle['problem_title']}\n"
        f"• {html.bold('Remaining Time:')} {remaining // 60}m {remaining % 60}s\n"
        f"Both players agreed to pause the battle."
    )
    await send_log(log_text, disable_notification=True)
    await callback_query.message.edit_text(
        f"⏸️ {html.bold('Battle Paused!')} ⏸️\n\n"
        f"🆔 {html.bold('Battle ID:')} {html.code(battle_id)}\n"
        f"Both players agreed to pause the battle. The timer has been frozen at {remaining // 60}m {remaining % 60}s.",
        parse_mode="HTML"
    )
    await callback_query.answer("Battle paused.")


@router.callback_query(F.data.startswith("pause_decline:"))
async def process_pause_decline(callback_query: CallbackQuery):
    parts = callback_query.data.split(":")
    battle_id = parts[1]
    target_opponent_id = int(parts[2])
    clicker_id = callback_query.from_user.id
    if clicker_id != target_opponent_id:
        await callback_query.answer("⚠️ Only the challenged opponent can decline the pause offer.", show_alert=True)
        return
    battle = await db.get_battle(battle_id)
    if not battle:
        await callback_query.answer("❌ Battle not found.", show_alert=True)
        return
    await callback_query.message.edit_text(
        f"❌ {html.bold('Pause Offer Declined!')}\n\n"
        f"🆔 {html.bold('Battle ID:')} {html.code(battle_id)}\n"
        f"Your opponent declined the pause offer. The battle continues active!",
        parse_mode="HTML"
    )
    await callback_query.answer("Pause offer declined.")


# Background task to monitor resume timeout
async def check_resume_timeout(bot, battle_id: str, initiator_id: int, opponent_id: int, paused_at_str: str):
    await asyncio.sleep(300) # 5 minutes
    
    battle = await db.get_battle(battle_id)
    if not battle or battle["status"] != "PAUSED":
        return
        
    db_paused_at = battle["paused_at"]
    if isinstance(db_paused_at, datetime.datetime):
        db_paused_at_str = db_paused_at.isoformat()
    else:
        db_paused_at_str = str(db_paused_at)
        
    if db_paused_at_str != paused_at_str:
        return

    now = datetime.datetime.now(datetime.timezone.utc)
    await db.update_battle_status(battle_id, "COMPLETED", winner_id=initiator_id, ended_at=now)
    await db.add_xp_coins(initiator_id, xp=100, coins=20)
    await db.add_xp_coins(opponent_id, xp=20, coins=0)
    
    w_row = await db.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", initiator_id)
    l_row = await db.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", opponent_id)
    w_name = w_row["first_name"] or w_row["username"] or "Challenger"
    l_name = l_row["first_name"] or l_row["username"] or "Opponent"

    from src.utils.logging_helper import send_log
    group_info = ""
    chat_id = battle.get("chat_id")
    if chat_id:
        if chat_id < 0:
            try:
                chat = await bot.get_chat(chat_id)
                group_title = chat.title or "Group"
                group_username = chat.username
            except Exception:
                group_title = "Group"
                group_username = None
                
            msg_id = battle.get("message_id")
            link = ""
            if msg_id:
                if group_username:
                    link = f"https://t.me/{group_username}/{msg_id}"
                elif str(chat_id).startswith("-100"):
                    link = f"https://t.me/c/{str(chat_id)[4:]}/{msg_id}"
                    
            if link:
                group_info = f"\n• {html.bold('Group:')} <a href='{link}'>{group_title}</a>"
            elif group_username:
                group_info = f"\n• {html.bold('Group:')} {group_title} (@{group_username})"
            else:
                group_info = f"\n• {html.bold('Group:')} {group_title} ({chat_id})"
        else:
            group_info = f"\n• {html.bold('Group:')} Private DM"

    log_text = (
        f"⏱️ {html.bold('LeetCode Battle Forfeited (Inactivity Resume Timeout)')} ⏱️\n\n"
        f"• {html.bold('Battle ID:')} {html.code(battle_id)}\n"
        f"• {html.bold('Problem:')} {battle['problem_title']}\n"
        f"• {html.bold('Winner:')} {w_name} ({initiator_id})\n"
        f"• {html.bold('Loser (Inactive):')} {l_name} ({opponent_id})"
        f"{group_info}"
    )
    await send_log(log_text, disable_notification=True)

    timeout_msg = (
        f"⏱️ {html.bold('Resume Request Timeout!')} 🚨\n\n"
        f"Battle ID: {html.code(battle_id)}\n"
        f"Player {html.bold(l_name)} failed to respond to the resume offer within 5 minutes and has forfeited.\n"
        f"🥇 Winner: {html.bold(w_name)} (Awarded 100 XP, 20 coins)\n"
        f"🥈 Loser: {html.bold(l_name)} (Awarded 20 XP)"
    )
    
    try:
        await bot.send_message(chat_id=initiator_id, text=timeout_msg, parse_mode="HTML")
        await bot.send_message(chat_id=opponent_id, text=timeout_msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error sending resume timeout alert: {e}")


@router.message(Command("resumebattle"))
async def cmd_resumebattle(message: Message, command: CommandObject):
    user_id = message.from_user.id
    battle = await get_battle_from_message_or_args(message, command)
    if not battle:
        rows = await db.fetch(
            "SELECT * FROM battles WHERE (challenger_id = $1 OR opponent_id = $1) AND status = 'PAUSED'",
            user_id
        )
        group_rows = await db.fetch(
            """
            SELECT DISTINCT gb.*
            FROM group_battles gb
            LEFT JOIN group_battle_participants gbp ON gb.id = gbp.group_battle_id
            WHERE (gbp.telegram_id = $1 OR gb.created_by = $1) AND gb.status = 'PAUSED'
            """,
            user_id
        )
        all_battles = [dict(r) for r in rows] + [dict(r) for r in group_rows]
        if len(all_battles) > 1:
            await message.reply("⚠️ You have multiple paused battles. Please specify the battle ID or reply to the battle message:\n`/resumebattle <battle_uuid>`")
            return
        elif len(all_battles) == 1:
            battle = all_battles[0]
        else:
            await message.reply("❌ You do not have any paused battles to resume.")
            return

    battle_id = str(battle["id"])
    is_group = "group_id" in battle
    remaining = battle["remaining_seconds"] or 3600
    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = now + datetime.timedelta(seconds=remaining)

    if is_group:
        role = await get_user_role(user_id, message.chat.id, message.chat.type, message.bot)
        has_admin_override = (role >= UserRole.GROUP_ADMIN) or (role >= UserRole.COORDINATOR)
        is_host = (user_id == battle["created_by"])
        if not is_host and not has_admin_override:
            await message.reply("❌ You do not have permission to resume this battle.")
            return
        if battle["status"] != "PAUSED":
            await message.reply(f"❌ Battle is not paused (Status: {battle['status']}).")
            return

        await db.execute(
            "UPDATE group_battles SET status = 'ACTIVE', paused_at = NULL, remaining_seconds = NULL, expires_at = $2 WHERE id = $1::uuid",
            battle_id, expires_at
        )
        await message.reply(
            f"▶️ {html.bold('Group Battle Resumed')} ▶️\n\n"
            f"🆔 Battle ID: {html.code(battle_id)}\n"
            f"Problem: {battle['problem_title']}\n\n"
            f"The battle has resumed! Timer continues at {remaining // 60}m {remaining % 60}s remaining.",
            parse_mode="HTML"
        )
        return

    is_player = (user_id == battle["challenger_id"] or user_id == battle["opponent_id"])
    role = await get_user_role(user_id, message.chat.id, message.chat.type, message.bot)
    has_admin_override = (role >= UserRole.GROUP_ADMIN) or (role >= UserRole.COORDINATOR)
    if not is_player and not has_admin_override:
        await message.reply("❌ You do not have permission to resume this battle.")
        return
    if battle["status"] != "PAUSED":
        await message.reply(f"❌ Battle is not paused (Status: {battle['status']}).")
        return

    battle_id = str(battle["id"])
    remaining = battle["remaining_seconds"] or 3600
    now = datetime.datetime.now(datetime.timezone.utc)

    if has_admin_override and not is_player:
        expires_at = now + datetime.timedelta(seconds=remaining)
        await db.execute(
            "UPDATE battles SET status = 'ACTIVE', paused_at = NULL, remaining_seconds = NULL, expires_at = $2 WHERE id = $1::uuid",
            battle_id, expires_at
        )
        from src.utils.logging_helper import log_admin_activity
        log_text = (
            f"▶️ {html.bold('Battle Forcefully Resumed by Admin')} ▶️\n\n"
            f"• {html.bold('Battle ID:')} {html.code(battle_id)}\n"
            f"• {html.bold('Problem:')} {battle['problem_title']}\n"
            f"• {html.bold('Resumed by:')} @{message.from_user.username or message.from_user.first_name} ({message.from_user.id})"
        )
        await log_admin_activity(log_text, message)
        await message.reply(
            f"▶️ {html.bold('Battle Forcefully Resumed')} ▶️\n\n"
            f"🆔 Battle ID: {html.code(battle_id)}\n"
            f"An administrator ({message.from_user.first_name}) has forcefully resumed this battle. Battle timer resumes at {remaining // 60}m {remaining % 60}s.",
            parse_mode="HTML"
        )
        return

    opponent_id = battle["opponent_id"] if user_id == battle["challenger_id"] else battle["challenger_id"]
    initiator_row = await db.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", user_id)
    opponent_row = await db.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", opponent_id)
    initiator_name = initiator_row["first_name"] or initiator_row["username"] or "Challenger"
    opponent_name = opponent_row["first_name"] or opponent_row["username"] or "Opponent"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="▶️ Accept Resume", callback_data=f"resume_accept:{battle_id}:{opponent_id}")
        ]
    ])
    db_paused_at = battle["paused_at"]
    if isinstance(db_paused_at, datetime.datetime):
        paused_at_str = db_paused_at.isoformat()
    else:
        paused_at_str = str(db_paused_at)

    await message.reply(
        f"▶️ {html.bold('Resume Request Proposed!')} ▶️\n\n"
        f"🆔 {html.bold('Battle ID:')} {html.code(battle_id)}\n"
        f"Player {html.bold(initiator_name)} wants to resume the battle.\n"
        f"Player {html.bold(opponent_name)}, please click the button below to accept and resume the battle.\n\n"
        f"⏳ You have {html.bold('5 minutes')} to accept, or you will forfeit and lose the battle!",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    asyncio.create_task(check_resume_timeout(message.bot, battle_id, user_id, opponent_id, paused_at_str))


@router.callback_query(F.data.startswith("resume_accept:"))
async def process_resume_accept(callback_query: CallbackQuery):
    parts = callback_query.data.split(":")
    battle_id = parts[1]
    target_opponent_id = int(parts[2])
    clicker_id = callback_query.from_user.id
    if clicker_id != target_opponent_id:
        await callback_query.answer("⚠️ Only the challenged opponent can accept the resume offer.", show_alert=True)
        return
    battle = await db.get_battle(battle_id)
    if not battle:
        await callback_query.answer("❌ Battle not found.", show_alert=True)
        return
    if battle["status"] != "PAUSED":
        await callback_query.answer(f"⚠️ Battle is already {battle['status'].lower()}.", show_alert=True)
        return
    remaining = battle["remaining_seconds"] or 3600
    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = now + datetime.timedelta(seconds=remaining)

    await db.execute(
        "UPDATE battles SET status = 'ACTIVE', paused_at = NULL, remaining_seconds = NULL, expires_at = $2 WHERE id = $1::uuid",
        battle_id, expires_at
    )
    from src.utils.logging_helper import send_log
    log_text = (
        f"▶️ {html.bold('LeetCode Battle Resumed')} ▶️\n\n"
        f"• {html.bold('Battle ID:')} {html.code(battle_id)}\n"
        f"• {html.bold('Problem:')} {battle['problem_title']}\n"
        f"• {html.bold('Remaining Time:')} {remaining // 60}m {remaining % 60}s"
    )
    await send_log(log_text, disable_notification=True)
    await callback_query.message.edit_text(
        f"▶️ {html.bold('Battle Resumed!')} ▶️\n\n"
        f"🆔 {html.bold('Battle ID:')} {html.code(battle_id)}\n"
        f"The battle for {html.bold(battle['problem_title'])} is now active again!\n"
        f"⏳ Remaining Time: {remaining // 60}m {remaining % 60}s.",
        parse_mode="HTML"
    )
    await callback_query.answer("Battle resumed.")


# --- Group Battles Callbacks ---

@router.callback_query(F.data.startswith("gbattle_join:"))
async def process_gbattle_join(callback_query: CallbackQuery):
    battle_id = callback_query.data.split(":")[1]
    battle = await db.get_group_battle(battle_id)
    if not battle:
        await callback_query.answer("⚠️ Battle not found.", show_alert=True)
        return
    if battle["status"] != "PENDING":
        await callback_query.answer(f"⚠️ This battle is already {battle['status'].lower()}.", show_alert=True)
        return
        
    user_id = callback_query.from_user.id
    user_row = await db.get_user(user_id)
    link = await db.get_linked_account(user_id)
    if not user_row or not link or not link["verified"]:
        bot_user = await callback_query.bot.get_me()
        await callback_query.answer(
            f"⚠️ You must register and verify your LeetCode account first! "
            f"Go to DM @{bot_user.username} and run /link.",
            show_alert=True
        )
        return
        
    joined = await db.join_group_battle(battle_id, user_id)
    if not joined:
        await callback_query.answer("ℹ️ You have already joined this battle!", show_alert=True)
        return
        
    await callback_query.answer("🎉 You have successfully joined the battle!")
    
    participants = await db.get_group_battle_participants(battle_id)
    part_list_str = "\n".join([f"{idx}. {p['first_name'] or p['username'] or str(p['telegram_id'])}" for idx, p in enumerate(participants, start=1)])
    
    creator_row = await db.get_user(battle["created_by"])
    creator_name = creator_row["first_name"] or creator_row["username"] if creator_row else "Challenger"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎮 Join Battle", callback_data=f"gbattle_join:{battle_id}"),
            InlineKeyboardButton(text="🏁 Start Battle", callback_data=f"gbattle_start:{battle_id}")
        ]
    ])
    
    updated_msg = (
        f"⚔️ {html.bold('LeetCode Group Battle Arena Open!')} ⚔️\n\n"
        f"🆔 {html.bold('Battle ID:')} {html.code(str(battle_id))}\n"
        f"👤 Host: {html.bold(creator_name)}\n"
        f"🏆 Problem Category: {html.bold(battle['difficulty'])}\n"
        f"⏳ Time Limit: {html.bold('60 minutes')} (once started)\n\n"
        f"👥 {html.bold('Participants Joined:')}\n{part_list_str}\n\n"
        f"👉 Click {html.bold('Join Battle')} below to enter the arena!\n"
        f"Host, click {html.bold('Start Battle')} once players have joined."
    )
    
    try:
        await callback_query.message.edit_text(updated_msg, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data.startswith("gbattle_start:"))
async def process_gbattle_start(callback_query: CallbackQuery):
    battle_id = callback_query.data.split(":")[1]
    battle = await db.get_group_battle(battle_id)
    if not battle:
        await callback_query.answer("⚠️ Battle not found.", show_alert=True)
        return
    if battle["status"] != "PENDING":
        await callback_query.answer(f"⚠️ This battle is already {battle['status'].lower()}.", show_alert=True)
        return
        
    clicker_id = callback_query.from_user.id
    from src.utils.roles import get_user_role, UserRole
    role = await get_user_role(clicker_id, callback_query.message.chat.id, callback_query.message.chat.type, callback_query.bot)
    if clicker_id != battle["created_by"] and role < UserRole.GROUP_ADMIN:
        await callback_query.answer("⚠️ Only the battle host or a group administrator can start this battle.", show_alert=True)
        return
        
    participants = await db.get_group_battle_participants(battle_id)
    if not participants:
        await callback_query.answer("⚠️ Cannot start battle. At least 1 participant must join first!", show_alert=True)
        return
        
    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = now + datetime.timedelta(hours=1)
    
    await db.update_group_battle_status(battle_id, "ACTIVE", starts_at=now, expires_at=expires_at)
    
    # Log group battle started to log channel
    try:
        from src.utils.logging_helper import send_log
        chat = callback_query.message.chat
        group_title = chat.title or "Group"
        group_username = chat.username
        msg_id = callback_query.message.message_id
        
        link = ""
        if group_username:
            link = f"https://t.me/{group_username}/{msg_id}"
        elif str(chat.id).startswith("-100"):
            link = f"https://t.me/c/{str(chat.id)[4:]}/{msg_id}"
            
        if link:
            group_info = f"<a href='{link}'>{group_title}</a>"
        elif group_username:
            group_info = f"{group_title} (@{group_username})"
        else:
            group_info = f"{group_title} ({chat.id})"
            
        log_text = (
            f"⚔️ {html.bold('Group LeetCode Battle Started')} ⚔️\n\n"
            f"• {html.bold('Battle ID:')} {html.code(str(battle_id))}\n"
            f"• {html.bold('Group:')} {group_info}\n"
            f"• {html.bold('Problem:')} {battle['problem_title']}\n"
            f"• {html.bold('Host:')} @{callback_query.from_user.username or callback_query.from_user.first_name} ({callback_query.from_user.id})\n"
            f"• {html.bold('Total Players:')} {len(participants)}"
        )
        await send_log(log_text, disable_notification=True)
    except Exception as log_err:
        logger.error(f"Error logging group battle start: {log_err}")
    
    battle_url = f"https://leetcode.com/problems/{battle['problem_slug']}"
    players_str = "\n".join([f"• {p['first_name'] or p['username'] or str(p['telegram_id'])} (⌛ Coding...)" for p in participants])
    
    start_msg = (
        f"⚔️ {html.bold('Group Battle Started!')} ⚔️\n\n"
        f"🆔 {html.bold('Battle ID:')} {html.code(str(battle_id))}\n"
        f"🏆 Problem: <a href='{battle_url}'>{battle['problem_title']}</a> ({battle['difficulty']})\n"
        f"⏳ Deadline: {html.code('60 minutes')} from now\n\n"
        f"👥 {html.bold('Players in Arena:')}\n{players_str}\n\n"
        f"🚀 Solve the problem on LeetCode and submit it! The bot will automatically check and compile the leaderboard."
    )
    
    verify_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Verify Solve", callback_data=f"gbattle_verify:{battle_id}")]
    ])
    await callback_query.message.edit_text(start_msg, reply_markup=verify_keyboard, parse_mode="HTML", disable_web_page_preview=True)
    await callback_query.answer("Battle started!")


@router.callback_query(F.data.startswith("battle_verify:"))
async def process_battle_verify(callback_query: CallbackQuery):
    battle_id = callback_query.data.split(":")[1]
    clicker_id = callback_query.from_user.id
    cooldown_key = (clicker_id, battle_id)
    now = datetime.datetime.now()
    if cooldown_key in VERIFY_COOLDOWNS:
        elapsed = (now - VERIFY_COOLDOWNS[cooldown_key]).total_seconds()
        if elapsed < 30:
            await callback_query.answer(f"⏱️ Please wait {int(30 - elapsed)}s before checking again.", show_alert=True)
            return
    
    battle = await db.get_battle(battle_id)
    if not battle:
        await callback_query.answer("⚠️ Battle not found.", show_alert=True)
        return
    if battle["status"] != "ACTIVE":
        await callback_query.answer(f"⚠️ This battle is not active (Status: {battle['status'].lower()}).", show_alert=True)
        return

    is_player = (clicker_id == battle["challenger_id"] or clicker_id == battle["opponent_id"])
    if not is_player:
        await callback_query.answer("⚠️ You are not a participant in this battle.", show_alert=True)
        return

    VERIFY_COOLDOWNS[cooldown_key] = now
    await callback_query.answer("Checking LeetCode submissions...")

    challenger_link = await db.get_linked_account(battle["challenger_id"])
    opponent_link = await db.get_linked_account(battle["opponent_id"])
    if not challenger_link or not opponent_link:
        await callback_query.message.reply("❌ Cannot verify solve: linked accounts not found.")
        return

    c_user = challenger_link["leetcode_username"]
    o_user = opponent_link["leetcode_username"]

    c_subs, o_subs = await asyncio.gather(
        leetcode_client.get_recent_accepted_submissions(c_user, limit=5),
        leetcode_client.get_recent_accepted_submissions(o_user, limit=5),
        return_exceptions=True
    )
    if isinstance(c_subs, Exception):
        logger.error(f"Error checking submissions for {c_user}: {c_subs}")
        c_subs = []
    if isinstance(o_subs, Exception):
        logger.error(f"Error checking submissions for {o_user}: {o_subs}")
        o_subs = []

    started_at = battle["started_at"]
    if isinstance(started_at, str):
        started_at = datetime.datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    elif started_at and started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=datetime.timezone.utc)

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
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        await db.update_battle_status(battle["id"], "COMPLETED", winner_id=winner_id, ended_at=now_utc)
        await db.add_xp_coins(winner_id, xp=100, coins=20)
        await db.add_xp_coins(loser_id, xp=20, coins=0)

        winner_row = await db.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", winner_id)
        loser_row = await db.fetchrow("SELECT username, first_name FROM users WHERE telegram_id = $1", loser_id)
        w_name = winner_row["first_name"] or winner_row["username"] or "Winner"
        l_name = loser_row["first_name"] or loser_row["username"] or "Loser"

        from src.utils.logging_helper import send_log
        log_text = (
            f"🏆 {html.bold('LeetCode Battle Won (Verify Solve Button)')} 🏆\n\n"
            f"• {html.bold('Battle ID:')} {html.code(str(battle['id']))}\n"
            f"• {html.bold('Problem:')} {battle['problem_title']}\n"
            f"• {html.bold('Winner:')} {w_name} ({winner_id})\n"
            f"• {html.bold('Loser:')} {l_name} ({loser_id})"
        )
        await send_log(log_text, disable_notification=True)

        winner_url = f"https://leetcode.com/problems/{battle['problem_slug']}"
        result_msg = (
            f"🎉 {html.bold('LeetCode Battle Completed!')} 🎉\n\n"
            f"🏆 Problem: <a href='{winner_url}'>{battle['problem_title']}</a>\n"
            f"🥇 Winner: {html.bold(w_name)} (Awarded 100 XP, 20 coins)\n"
            f"🥈 Loser: {html.bold(l_name)} (Awarded 20 XP)\n\n"
            f"Congratulations to both players for competing!"
        )

        try:
            await callback_query.message.edit_text(result_msg, parse_mode="HTML", disable_web_page_preview=True)
        except Exception:
            pass
        try:
            await callback_query.bot.send_message(chat_id=battle["challenger_id"], text=result_msg, parse_mode="HTML", disable_web_page_preview=True)
            await callback_query.bot.send_message(chat_id=battle["opponent_id"], text=result_msg, parse_mode="HTML", disable_web_page_preview=True)
        except Exception:
            pass
    else:
        await callback_query.message.reply(
            f"❌ {html.bold('Verification Failed')}\n\n"
            f"We checked both players but did not find any accepted submission for "
            f"{html.bold(battle['problem_title'])} on LeetCode since the battle started.\n"
            f"Make sure to solve it first and wait a few seconds for LeetCode to save your submission!",
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("gbattle_verify:"))
async def process_gbattle_verify(callback_query: CallbackQuery):
    battle_id = callback_query.data.split(":")[1]
    clicker_id = callback_query.from_user.id
    cooldown_key = (clicker_id, battle_id)
    now = datetime.datetime.now()
    if cooldown_key in VERIFY_COOLDOWNS:
        elapsed = (now - VERIFY_COOLDOWNS[cooldown_key]).total_seconds()
        if elapsed < 30:
            await callback_query.answer(f"⏱️ Please wait {int(30 - elapsed)}s before checking again.", show_alert=True)
            return

    battle = await db.get_group_battle(battle_id)
    if not battle:
        await callback_query.answer("⚠️ Battle not found.", show_alert=True)
        return
    if battle["status"] != "ACTIVE":
        await callback_query.answer(f"⚠️ This battle is not active (Status: {battle['status'].lower()}).", show_alert=True)
        return

    participants = await db.get_group_battle_participants(battle_id)
    is_part = any(p["telegram_id"] == clicker_id for p in participants)
    if not is_part:
        await callback_query.answer("⚠️ You are not a participant in this group battle.", show_alert=True)
        return

    VERIFY_COOLDOWNS[cooldown_key] = now
    await callback_query.answer("Checking LeetCode submissions...")

    unsolved_parts = [p for p in participants if p["solved_at"] is None]
    if not unsolved_parts:
        await callback_query.answer("All participants have already solved this problem.")
        return

    telegram_ids = [p["telegram_id"] for p in unsolved_parts]
    user_to_leetcode = await db.get_verified_links_for_users(telegram_ids)

    async def check_user_sub(p):
        tg_id = p["telegram_id"]
        leetcode_user = user_to_leetcode.get(tg_id)
        if not leetcode_user:
            return None
        try:
            subs = await leetcode_client.get_recent_accepted_submissions(leetcode_user, limit=5)
            return tg_id, subs
        except Exception as e:
            logger.error(f"Error checking submissions for group player {leetcode_user}: {e}")
            return tg_id, []

    results = await asyncio.gather(*[check_user_sub(p) for p in unsolved_parts])
    user_subs_map = {r[0]: r[1] for r in results if r is not None}

    starts_at = battle["starts_at"]
    if isinstance(starts_at, str):
        starts_at = datetime.datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
    elif starts_at and starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=datetime.timezone.utc)

    solves_updated = False

    for p in unsolved_parts:
        tg_id = p["telegram_id"]
        subs = user_subs_map.get(tg_id, [])
        for sub in subs:
            if sub["titleSlug"] == battle["problem_slug"]:
                sub_time = datetime.datetime.fromtimestamp(int(sub["timestamp"]), tz=datetime.timezone.utc)
                if sub_time > starts_at:
                    solve_time = int((sub_time - starts_at).total_seconds())
                    await db.update_group_participant_solve(battle_id, tg_id, sub_time, solve_time)
                    p["solved_at"] = sub_time
                    p["solve_time_seconds"] = solve_time
                    solves_updated = True

                    solved_msg = (
                        f"🎉 {html.bold('LeetCode Group Battle Solve!')} 🏆\n\n"
                        f"• Player: <a href='tg://user?id={tg_id}'>{p['first_name'] or p['username']}</a>\n"
                        f"• Problem: {battle['problem_title']}\n"
                        f"• Time Taken: {solve_time // 60}m {solve_time % 60}s\n\n"
                        f"Great job! Keep it up! 💪"
                    )
                    try:
                        await callback_query.message.bot.send_message(chat_id=battle["group_id"], text=solved_msg, parse_mode="HTML")
                    except Exception as e:
                        logger.error(f"Error sending solve notification: {e}")
                    break

    participants = await db.get_group_battle_participants(battle_id)
    all_solved = all(p["solved_at"] is not None for p in participants)
    if all_solved and solves_updated:
        await db.update_group_battle_status(battle_id, "COMPLETED")
        from src.main import end_group_battle
        await end_group_battle(battle, participants, expired=False)
        try:
            await callback_query.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    elif solves_updated:
        battle_url = f"https://leetcode.com/problems/{battle['problem_slug']}"
        refreshed_players = []
        for p in participants:
            if p["solved_at"] is not None:
                st = p["solve_time_seconds"]
                refreshed_players.append(f"• {p['first_name'] or p['username']} (✅ Solved in {st // 60}m {st % 60}s)")
            else:
                refreshed_players.append(f"• {p['first_name'] or p['username']} (⌛ Coding...)")
        players_str = "\n".join(refreshed_players)

        start_msg = (
            f"⚔️ {html.bold('Group Battle Started!')} ⚔️\n\n"
            f"🆔 {html.bold('Battle ID:')} {html.code(str(battle_id))}\n"
            f"🏆 Problem: <a href='{battle_url}'>{battle['problem_title']}</a> ({battle['difficulty']})\n"
            f"⏳ Deadline: {html.code('60 minutes')} from now\n\n"
            f"👥 {html.bold('Players in Arena:')}\n{players_str}\n\n"
            f"🚀 Solve the problem on LeetCode and submit it! The bot will automatically check and compile the leaderboard."
        )

        verify_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Verify Solve", callback_data=f"gbattle_verify:{battle_id}")]
        ])
        try:
            await callback_query.message.edit_text(start_msg, reply_markup=verify_keyboard, parse_mode="HTML", disable_web_page_preview=True)
        except Exception:
            pass
    else:
        await callback_query.message.reply(
            f"❌ {html.bold('Verification Failed')}\n\n"
            f"We checked all active players but did not find any new accepted submissions for "
            f"{html.bold(battle['problem_title'])} on LeetCode since the battle started.\n"
            f"Make sure to solve it on LeetCode first!",
            parse_mode="HTML"
        )

