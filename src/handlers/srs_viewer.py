import logging
import datetime
from aiogram import Router, F, html
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from src.services.supabase_db import db
from src.services.redis_cache import cache_manager

router = Router()
logger = logging.getLogger(__name__)

def build_reviews_message_and_keyboard(reviews: list):
    if not reviews:
        msg = "🎉 You have no spaced repetition reviews scheduled! Use `/solved` to schedule a problem."
        return msg, None

    current_date = datetime.datetime.now(datetime.timezone.utc).date()
    due_items = []
    upcoming_items = []

    for r in reviews:
        dt = r["next_review_date"]
        # Convert offset-naive or offset-aware datetime to UTC date
        if dt.tzinfo is None:
            item_date = dt.date()
        else:
            item_date = dt.astimezone(datetime.timezone.utc).date()

        if item_date <= current_date:
            due_items.append(r)
        else:
            upcoming_items.append(r)

    msg = f"🧠 {html.bold('Your Spaced Repetition Queue')}\n\n"
    
    if due_items:
        msg += f"🚨 {html.bold('Due for Review:')}\n"
        for item in due_items:
            date_str = item["next_review_date"].strftime("%d %b %Y")
            difficulty = item.get("difficulty") or "Medium"
            diff_emoji = "🟢" if difficulty == "Easy" else "🟡" if difficulty == "Medium" else "🔴"
            msg += f"• {diff_emoji} {html.bold(item['problem_title'])} (Due: {html.code(date_str)})\n"
    
    if upcoming_items:
        if due_items:
            msg += "\n"
        msg += f"📅 {html.bold('Upcoming Reviews:')}\n"
        for item in upcoming_items[:10]: # Show next 10 upcoming to keep message concise
            date_str = item["next_review_date"].strftime("%d %b %Y")
            difficulty = item.get("difficulty") or "Medium"
            diff_emoji = "🟢" if difficulty == "Easy" else "🟡" if difficulty == "Medium" else "🔴"
            msg += f"• {diff_emoji} {item['problem_title']} (Due: {html.code(date_str)})\n"
        if len(upcoming_items) > 10:
            msg += f"• {html.italic(f'and {len(upcoming_items) - 10} more upcoming...')}\n"

    # Create inline keyboard for mastering
    keyboard_buttons = []
    # Prioritize showing due items in the Mastered buttons first, then upcoming
    all_display_items = due_items + upcoming_items
    for item in all_display_items[:6]: # Limit to 6 buttons to avoid keyboard bloat
        btn_text = f"✅ Master: {item['problem_title']}"
        keyboard_buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"srs_master:{item['problem_slug']}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons) if keyboard_buttons else None
    return msg, keyboard


@router.message(Command("reviews"))
async def cmd_reviews(message: Message):
    user_id = message.from_user.id
    if await cache_manager.is_rate_limited(user_id, "reviews", limit=5, period=10):
        await message.reply("Please wait a moment.")
        return

    try:
        # Check if LeetCode is linked
        link = await db.get_linked_account(user_id)
        if not link or not link["verified"]:
            await message.reply(f"⚠️ You must link and verify your LeetCode account first using {html.code('/link <username>')}!", parse_mode="HTML")
            return

        reviews = await db.get_user_srs_reviews(user_id)
        msg, keyboard = build_reviews_message_and_keyboard(reviews)
        
        await message.reply(msg, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in reviews command: {e}", exc_info=True)
        await message.reply("❌ An unexpected error occurred while fetching your reviews.")


@router.callback_query(F.data.startswith("srs_master:"))
async def process_srs_master(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    problem_slug = callback_query.data.split(":")[1]

    try:
        # Fetch problem details to confirm title
        reviews = await db.get_user_srs_reviews(user_id)
        review_item = next((r for r in reviews if r["problem_slug"] == problem_slug), None)
        problem_title = review_item["problem_title"] if review_item else problem_slug

        # Delete review
        await db.delete_srs_review(user_id, problem_slug)
        await callback_query.answer(f"🎉 Marked {problem_title} as Mastered!")

        # Refresh queue
        updated_reviews = await db.get_user_srs_reviews(user_id)
        msg, keyboard = build_reviews_message_and_keyboard(updated_reviews)
        
        await callback_query.message.edit_text(msg, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in srs_master callback: {e}", exc_info=True)
        await callback_query.answer("❌ Failed to process mastering. Please try again.", show_alert=True)


@router.callback_query(F.data == "cmd_reviews")
async def process_cmd_reviews_button(callback_query: CallbackQuery):
    """Handle the 📋 View Reviews Queue button from the daily SRS reminder DM."""
    user_id = callback_query.from_user.id
    await callback_query.answer()

    try:
        link = await db.get_linked_account(user_id)
        if not link or not link["verified"]:
            await callback_query.message.answer(
                f"⚠️ You must link and verify your LeetCode account first using <code>/link &lt;username&gt;</code>!",
                parse_mode="HTML"
            )
            return

        reviews = await db.get_user_srs_reviews(user_id)
        msg, keyboard = build_reviews_message_and_keyboard(reviews)
        await callback_query.message.answer(msg, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in cmd_reviews callback: {e}", exc_info=True)
        await callback_query.message.answer("❌ An unexpected error occurred while fetching your reviews.")
