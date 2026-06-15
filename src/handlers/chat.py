"""
Rule-based conversational fallback handler.

Registered last in the router chain — catches any text message that wasn't
handled by a more specific command/handler and tries to give a useful,
topic-based reply based on keyword matching + short-term conversational
context stored in Redis.
"""

import logging
import re
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.bot import Bot

from src.services.redis_cache import cache_manager

router = Router()
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

RATE_LIMIT_COUNT = 5
RATE_LIMIT_PERIOD_SECONDS = 60
CONTEXT_TTL_SECONDS = 300

# Topics that have a dedicated follow-up reply and should be persisted
# verbatim into the conversational context cache.
TOPIC_KEYS_WITH_CONTEXT = {"battles", "srs", "ai", "streak", "link"}

# --------------------------------------------------------------------------- #
# Topic Response Contents (Telegram-compatible HTML)
# --------------------------------------------------------------------------- #

TOPIC_RESPONSES = {
    "about": (
        "🤖 <b>About Memoize</b>\n\n"
        "I am a Telegram-native coding assistant built to make LeetCode practice a collaborative, high-retention habit!\n\n"
        "<b>Key Features:</b>\n"
        "• 🧠 <b>Spaced Repetition (SRS):</b> Logs solved problems and automatically schedules reviews using the SuperMemo SM-2 algorithm to beat the forgetting curve.\n"
        "• ⚔️ <b>Coding Battles:</b> Start 1v1 speed battles or open group challenges where users solve the same problem to climb the leaderboard.\n"
        "• 🤖 <b>AI Coaching:</b> Get step-by-step hints (/hint), Big-O complexity analysis (/analyze), and code reviews (/review) without spoiling the answers.\n\n"
        "Ready to practice? Type /daily to view today's challenge! 🏆"
    ),
    "battles": (
        "⚔️ <b>Coding Battles Guide</b>\n\n"
        "Challenge your peers to real-time coding sprints! The bot automatically tracks LeetCode submissions to determine the winner.\n\n"
        "<b>How it works:</b>\n"
        "• <b>1v1 Battles:</b> Challenge a peer in a group chat using <code>/battle @username</code>. If they accept, you both get 60 minutes to solve a random problem.\n"
        "• <b>Multiplayer Open Battles:</b> Launch a lobby in a group using <code>/battle open [difficulty] [tag]</code>. Anyone in the group can click <i>Join Battle</i>, and the creator can click <i>Start Battle</i> to lock the lobby and start the 60-minute timer.\n"
        "• <b>Rewards:</b> Winners earn up to 150 XP and 30 coins, while losers or other participants still receive completion XP!\n\n"
        "<i>Reply with \"how to play\" for setup instructions.</i>"
    ),
    "srs": (
        "🧠 <b>Spaced Repetition (SRS) System</b>\n\n"
        "I use the SuperMemo SM-2 algorithm to schedule review dates for your solved LeetCode problems based on how well you recalled the solution.\n\n"
        "<b>How it works:</b>\n"
        "1. Solve a problem on LeetCode.\n"
        "2. Send <code>/solved</code> to the bot. It will fetch your recent submissions.\n"
        "3. Click on the problem and rate your recall quality from <b>0 (Forgot completely)</b> to <b>5 (Perfect recall)</b>.\n"
        "4. I will calculate and set your next review date. I'll automatically DM you at 9:00 AM local time when a review is due!\n\n"
        "<i>Reply with \"how to rate\" to learn about the grading scale.</i>"
    ),
    "ai": (
        "🤖 <b>AI Coaching Features</b>\n\n"
        "Get algorithmic guidance and feedback directly in your chat without exposing full solutions!\n\n"
        "<b>AI Commands:</b>\n"
        "• <code>/hint &lt;problem_slug&gt;</code> — Generates progressive, step-by-step hints (Conceptual ➡️ Strategic ➡️ Pseudocode) via Groq (Llama 3.3).\n"
        "• <code>/analyze</code> — Analyzes a pasted code block (or replied code) for time and space complexity.\n"
        "• <code>/review</code> — Audits code quality, style, and correctness using Gemini Flash 2.0.\n"
        "• <code>/visualize</code> — Generates a control flow Mermaid diagram and step-by-step trace of your code execution.\n\n"
        "<i>Reply with \"how to use AI\" for prompt tips.</i>"
    ),
    "streak": (
        "🔥 <b>Streak Systems</b>\n\n"
        "I track two kinds of coding streaks to keep you disciplined:\n\n"
        "• <b>LeetCode Calendar Streak:</b> Check your active coding streak directly from your official LeetCode profile using <code>/streak</code>.\n"
        "• <b>Daily Challenge Streak:</b> Check your consecutive Daily Challenge solves recorded in the bot's database using <code>/dstreak</code>.\n"
        "• <b>Automatic Checkers:</b> Every day at 15:00 UTC, the bot automatically checks if you solved a problem on LeetCode. If you solved one, it auto-logs it to protect your streak. If not, it sends you a warning DM so you don't break the chain! You can toggle these alerts in <code>/reminders</code>."
    ),
    "link": (
        "🔗 <b>LeetCode Account Linking & Verification</b>\n\n"
        "To start using features like coding battles, SRS logging, and streak tracking, you need to connect your LeetCode account to your Telegram ID.\n\n"
        "<b>Commands:</b>\n"
        "• <code>/link &lt;leetcode_username&gt;</code> — Set your LeetCode username.\n"
        "• <code>/verify</code> — Verify account ownership by updating your LeetCode bio.\n"
        "• <code>/unlink</code> — Disconnect your LeetCode profile from the bot.\n"
        "• <code>/profile</code> — View your stats, XP, and active account settings.\n\n"
        "<i>Reply with \"how to link\" for verification troubleshooting.</i>"
    ),
}

# Context-Specific Follow-ups
CONTEXT_FOLLOW_UPS = {
    "battles": (
        "🎮 <b>How to Start a Coding Battle:</b>\n\n"
        "1. Ensure both you and your opponent have linked and verified your accounts using <code>/link</code> and <code>/verify</code>.\n"
        "2. In a group chat, type <code>/battle @username</code> or <code>/battle open</code>.\n"
        "3. Accept the challenge via the inline buttons.\n"
        "4. Once active, solve the problem on LeetCode. The bot checks submissions every minute and awards the win automatically!"
    ),
    "srs": (
        "📊 <b>SRS Recall Quality Grading Scale:</b>\n\n"
        "• <b>5 (Perfect):</b> Perfect recall, solved instantly.\n"
        "• <b>4 (Good):</b> Correct solution, required minor thinking.\n"
        "• <b>3 (Okay):</b> Correct solution, but required significant effort.\n"
        "• <b>2 (Difficult):</b> Incorrect solution, but remembered key parts.\n"
        "• <b>1 (Bad):</b> Incorrect, only remembered the general idea.\n"
        "• <b>0 (Forgot):</b> Total blackout.\n\n"
        "Grading 3 or higher schedules longer review intervals. Grading 0-2 resets the repetition count and schedules review for tomorrow."
    ),
    "ai": (
        "💡 <b>Tips for AI Commands:</b>\n\n"
        "• You can use AI commands by passing the code directly: <code>/analyze def solution(): ...</code>\n"
        "• Or, write the command as a <b>reply</b> to any message containing a code block. This is the cleanest way in group chats!\n"
        "• AI coach hints are private in DMs so you don't spoil answers in group channels."
    ),
    "link": (
        "💡 <b>Linking & Verification Troubleshooting:</b>\n\n"
        "• <b>Bio changes cache:</b> LeetCode can sometimes cache user profile pages. If verification fails, wait 1-2 minutes and run <code>/verify</code> again.\n"
        "• <b>Token placement:</b> Make sure the token is copied exactly as shown and pasted into your LeetCode bio settings, then save the changes on the LeetCode website before running <code>/verify</code> again."
    ),
}

GREETING_MESSAGE = (
    "👋 <b>Hello there!</b>\n\n"
    "I am <b>Memoize</b>, your LeetCode and DSA companion bot. I'm here to help you build coding discipline, track your spaced repetition reviews, challenge friends to speed battles, and coach you on logic!\n\n"
    "Type /help to see all available commands, or link your LeetCode account with /link to get started! 🚀"
)

THANKS_MESSAGE = (
    "😊 <b>You're very welcome!</b>\n\n"
    "I'm always happy to help. Keep coding and crush those LeetCode problems! If you need anything else, just ask or select a topic below."
)

BYE_MESSAGE = (
    "👋 <b>Goodbye!</b>\n\n"
    "Happy coding! Don't forget to maintain your streaks and review your pending SRS questions. See you next time! 🚀"
)

AFFIRMATION_MESSAGE = (
    "👍 <b>Got it!</b>\n\n"
    "Let me know if you want to explore any features or need help with LeetCode practice. Select a topic below to get started! 👇"
)

GENERIC_FALLBACK_MESSAGE = (
    "🤖 <b>I am your LeetCode Companion bot.</b>\n\n"
    "I didn't quite catch that, but I can help you with commands and guides. Choose a topic below to learn more! 👇"
)

GROUP_MENTION_ONLY_MESSAGE_TEMPLATE = (
    "Hello! I am @{username}, your LeetCode Companion bot. Ask me questions about "
    "DSA, coding battles, or use commands like /help!"
)

# --------------------------------------------------------------------------- #
# Keyword sets (including common plurals for robust matching)
# --------------------------------------------------------------------------- #

GREETING_WORDS = {"hi", "hello", "hey", "yo", "sup", "greetings", "namaste", "hola", "morning", "evening", "welcome", "gday"}
ABOUT_WORDS = {"who", "what", "purpose", "creator", "memoize", "bot"}
BATTLE_WORDS = {"battle", "battles", "fight", "fights", "1v1", "challenge", "challenges", "multiplayer", "compete", "competitions", "play", "lobby", "lobbies", "versus", "vs", "match", "game", "arena", "duel", "duels", "room", "rooms"}
SRS_WORDS = {"solved", "log", "logs", "review", "reviews", "srs", "spaced", "repetition", "sm2", "memory", "retention", "rate", "rates", "recall", "rating", "grading", "schedule", "schedules", "memorize", "forgetting", "curve"}
AI_WORDS = {"ai", "hint", "hints", "complexity", "analyze", "flowchart", "flowcharts", "visualize", "reviewcode", "coach", "assistant", "explanation", "explain", "gemini", "llama", "groq", "big-o", "trace", "diagram"}
STREAK_WORDS = {"streak", "streaks", "consecutive", "active", "dstreak", "daily", "chain", "calendar", "days", "record"}
LINK_WORDS = {"link", "verify", "unlink", "authenticate", "connect", "username", "profile", "auth", "login", "register", "bio", "token", "account", "accounts"}
FOLLOW_UP_WORDS = {"how", "use", "start", "rules", "quality", "schedule", "grades", "run", "paste", "prompt", "setup", "troubleshoot", "troubleshooting", "fix", "fail", "fails"}

# Sentiment keyword sets
THANKS_WORDS = {"thanks", "thank", "ty", "appreciate", "helpful", "awesome", "cool", "nice", "great", "wonderful"}
BYE_WORDS = {"bye", "goodbye", "cya", "adios", "farewell"}
BYE_PHRASES = ("see you",)
AFFIRMATION_WORDS = {"yes", "yeah", "yup", "yep", "ok", "okay", "sure", "indeed", "correct", "agree", "agreed"}

# Ordered topic-matching table: checked top-to-bottom, first match wins.
# Specific feature topics are checked before generic greeting/about topics
# so that e.g. "what's my streak?" resolves to the streak guide, not "about".
TOPIC_KEYWORD_PRIORITY: list[tuple[str, set[str], str]] = [
    ("link", LINK_WORDS, TOPIC_RESPONSES["link"]),
    ("battles", BATTLE_WORDS, TOPIC_RESPONSES["battles"]),
    ("srs", SRS_WORDS, TOPIC_RESPONSES["srs"]),
    ("ai", AI_WORDS, TOPIC_RESPONSES["ai"]),
    ("streak", STREAK_WORDS, TOPIC_RESPONSES["streak"]),
    ("general", GREETING_WORDS, GREETING_MESSAGE),
    ("general", ABOUT_WORDS, TOPIC_RESPONSES["about"]),
]

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

# Cache bot usernames per-bot-id so we don't hit get_me() on every message.
_bot_username_cache: dict[int, str] = {}


async def _get_bot_username(bot: Bot) -> str:
    """Return (and cache) the bot's @username."""
    if bot.id not in _bot_username_cache:
        me = await bot.get_me()
        _bot_username_cache[bot.id] = me.username
    return _bot_username_cache[bot.id]


def get_chat_help_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="ℹ️ About Bot", callback_data="chat_help:about"),
            InlineKeyboardButton(text="🔗 Link Profile", callback_data="chat_help:link"),
        ],
        [
            InlineKeyboardButton(text="⚔️ Battles Guide", callback_data="chat_help:battles"),
            InlineKeyboardButton(text="🧠 SRS Reviews", callback_data="chat_help:srs"),
        ],
        [
            InlineKeyboardButton(text="🤖 AI Features", callback_data="chat_help:ai"),
            InlineKeyboardButton(text="🔥 Streaks Info", callback_data="chat_help:streak"),
        ],
    ])


async def _send_topic_reply(message: Message, history_key: str, topic_key: str, content: str) -> None:
    """Persist conversational context and send a topic reply with the help keyboard."""
    await cache_manager.set(history_key, topic_key, expire_seconds=CONTEXT_TTL_SECONDS)
    await message.reply(content, parse_mode="HTML", reply_markup=get_chat_help_keyboard())


def _extract_prompt_text(message_text: str, bot_username: str, is_private: bool) -> Optional[str]:
    """
    Return the text to analyse, or None if this message shouldn't be
    handled at all (group message without a mention).
    """
    if is_private:
        return message_text.strip()

    # In groups, only trigger if the bot is explicitly @-mentioned
    # (case-insensitive, since Telegram usernames are case-insensitive).
    mention_pattern = re.compile(re.escape(f"@{bot_username}"), re.IGNORECASE)
    if not mention_pattern.search(message_text):
        return None

    return mention_pattern.sub("", message_text).strip()


# --------------------------------------------------------------------------- #
# Handlers
# --------------------------------------------------------------------------- #

@router.message(F.text, ~F.text.startswith("/"))
async def fallback_chat_handler(message: Message) -> None:
    """Rule-based conversational fallback handler."""
    is_private = message.chat.type == "private"
    user_id = message.from_user.id

    bot_username = await _get_bot_username(message.bot)
    prompt_text = _extract_prompt_text(message.text, bot_username, is_private)

    if prompt_text is None:
        # Group message that didn't @-mention the bot — ignore entirely.
        return

    # Rate limit before doing any further work, so repeated bare mentions
    # or empty pings in groups can't be used to spam this handler.
    if await cache_manager.is_rate_limited(user_id, "chat_fallback", limit=RATE_LIMIT_COUNT, period=RATE_LIMIT_PERIOD_SECONDS):
        await message.reply("⚠️ You're sending messages too fast. Please wait a moment.")
        return

    if not prompt_text:
        if not is_private:
            # Mentioned in a group with no other text.
            await message.reply(
                GROUP_MENTION_ONLY_MESSAGE_TEMPLATE.format(username=bot_username),
                reply_markup=get_chat_help_keyboard(),
            )
        # In private chats, a blank/whitespace-only message gets no reply.
        return

    # Tokenize the user input to find matches
    words = set(re.findall(r"\b\w+\b", prompt_text.lower()))

    history_key = f"chat_topic:{user_id}"

    # 1. Check for context-aware follow-up first
    active_context = await cache_manager.get(history_key)
    if active_context and active_context in CONTEXT_FOLLOW_UPS and (words & FOLLOW_UP_WORDS):
        await cache_manager.set(history_key, active_context, expire_seconds=CONTEXT_TTL_SECONDS)  # Refresh TTL
        await message.reply(CONTEXT_FOLLOW_UPS[active_context], parse_mode="HTML", reply_markup=get_chat_help_keyboard())
        return

    # 2. Check for sentiment (gratitude & goodbyes)
    if words & THANKS_WORDS:
        await _send_topic_reply(message, history_key, "general", THANKS_MESSAGE)
        return

    if (words & BYE_WORDS) or any(phrase in prompt_text.lower() for phrase in BYE_PHRASES):
        await _send_topic_reply(message, history_key, "general", BYE_MESSAGE)
        return

    if words & AFFIRMATION_WORDS:
        await _send_topic_reply(message, history_key, "general", AFFIRMATION_MESSAGE)
        return

    # 3. Match main keywords (specific topics first, general about/greetings last)
    for topic_key, keyword_set, response in TOPIC_KEYWORD_PRIORITY:
        if words & keyword_set:
            await _send_topic_reply(message, history_key, topic_key, response)
            return

    # 4. Generic fallback
    await _send_topic_reply(message, history_key, "general", GENERIC_FALLBACK_MESSAGE)


@router.callback_query(F.data.startswith("chat_help:"))
async def on_chat_help_callback(callback: CallbackQuery) -> None:
    topic = callback.data.split(":")[1]

    response = TOPIC_RESPONSES.get(topic)
    if response is None:
        await callback.answer()
        return

    user_id = callback.from_user.id
    history_key = f"chat_topic:{user_id}"
    topic_key = topic if topic in TOPIC_KEYS_WITH_CONTEXT else "general"

    await cache_manager.set(history_key, topic_key, expire_seconds=CONTEXT_TTL_SECONDS)
    await callback.message.edit_text(response, parse_mode="HTML", reply_markup=get_chat_help_keyboard())
    await callback.answer()