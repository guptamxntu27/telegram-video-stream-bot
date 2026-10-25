import os
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")
ADMIN_ID = os.getenv("ADMIN_ID", "")


def is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(
        user
        and ADMIN_ID
        and str(user.id) == ADMIN_ID
    )


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_admin(update):
        await update.effective_message.reply_text(
            "⛔ यह बॉट केवल Admin के लिए है।"
        )
        return

    await update.effective_message.reply_text(
        "🎬 Telegram Video Bot तैयार है!\n\n"
        "वीडियो भेजें। मैं उसे आपके Private Channel में सेव करूँगा।\n\n"
        "वीडियो के Caption में उसका नाम लिख सकते हैं।\n\n"
        "Commands:\n"
        "/start - Bot शुरू करें\n"
        "/help - मदद\n"
        "/id - अपना Telegram ID देखें"
    )


async def show_id(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user

    if user:
        await update.effective_message.reply_text(
            f"आपका Telegram ID: {user.id}"
        )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_admin(update):
        await update.effective_message.reply_text(
            "⛔ केवल Admin इस बॉट का उपयोग कर सकता है।"
        )
        return

    await update.effective_message.reply_text(
        "📖 मदद\n\n"
        "1. वीडियो सीधे बॉट को भेजें।\n"
        "2. वीडियो का नाम Caption में लिख सकते हैं।\n"
        "3. बॉट वीडियो को Private Channel में सेव करेगा।\n\n"
        "ध्यान दें: Player और Download लिंक के लिए "
        "Streaming Backend सेटअप करना बाकी है।"
    )


async def receive_video(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not is_admin(update):
        await message.reply_text(
            "⛔ आपको इस बॉट का उपयोग करने की अनुमति नहीं है।"
        )
        return

    if not CHANNEL_ID:
        await message.reply_text(
            "⚠️ CHANNEL_ID सेट नहीं है। Render में "
            "Environment Variables जाँचें।"
        )
        return

    try:
        saved_message = await context.bot.copy_message(
            chat_id=int(CHANNEL_ID),
            from_chat_id=message.chat_id,
            message_id=message.message_id,
        )

        video_name = (
            message.caption
            or (
                message.video.file_name
                if message.video and message.video.file_name
                else None
            )
            or (
                message.document.file_name
                if message.document and message.document.file_name
                else None
            )
            or "Video"
        )

        await message.reply_text(
            "✅ वीडियो Private Channel में सेव हो गया!\n\n"
            f"🎬 नाम: {video_name[:200]}\n"
            f"🆔 Saved Message ID: {saved_message.message_id}\n\n"
            "▶️ Player Link: अभी सेटअप नहीं हुआ है।\n"
            "📥 Download Link: अभी सेटअप नहीं हुआ है।\n\n"
            "अगला चरण: Streaming Backend सेटअप करना।"
        )

    except Exception:
        logger.exception("Video save failed")
        await message.reply_text(
            "❌ वीडियो सेव नहीं हो सका।\n\n"
            "कृपया जाँचें:\n"
            "1. CHANNEL_ID सही है।\n"
            "2. Bot Private Channel में Admin है।\n"
            "3. Bot को Channel में पोस्ट करने की अनुमति है।"
        )


def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN Environment Variable सेट नहीं है।"
        )

    if not ADMIN_ID:
        raise RuntimeError(
            "ADMIN_ID Environment Variable सेट नहीं है।"
        )

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("id", show_id))

    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE
            & (filters.VIDEO | filters.Document.VIDEO),
            receive_video,
        )
    )

    logger.info("Telegram Video Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
