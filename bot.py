"""
KING MULTIVERSE Telegram Bot
============================
Bot: @KING_Multiverse_Robot

Deploy on Render:
  - Set env vars: BOT_TOKEN, API_ID, API_HASH
  - Start command: python bot.py
"""

import os
import threading
import logging
from flask import Flask, jsonify
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------------------------------------------------------------------------
# CONFIG — all secrets come from environment variables (set on Render)
# ---------------------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
API_ID = os.environ.get("API_ID", "")
API_HASH = os.environ.get("API_HASH", "")
BOT_USERNAME = "KING_Multiverse_Robot"

BANNER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Tg_Banner.jpg")
CHANNEL_URL = "https://t.me/ModAppsKing"
GROUP_URL = "https://t.me/ANONYMOUS_GROUP_KING"
PORT = int(os.environ.get("PORT", 10000))
# ---------------------------------------------------------------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "👋 Hello {name}!\n\n"
    "Welcome to *KING MULTIVERSE* Bot.\n\n"
    "🚀 For the best experience, premium mod apps, games, tools "
    "and fast updates please use our official Channel:\n\n"
    "🌐 {url}\n\n"
    "Enjoy premium apps for free and keep modding! 🚀"
)


# ---------------------------------------------------------------------------
# Flask keep-alive web server (required by Render free tier)
# ---------------------------------------------------------------------------
app_flask = Flask(__name__)


@app_flask.route("/")
def home():
    return jsonify(
        {
            "status": "running",
            "bot": f"@{BOT_USERNAME}",
            "channel": CHANNEL_URL,
        }
    )


@app_flask.route("/health")
def health():
    return jsonify({"status": "ok"})


def run_flask():
    app_flask.run(host="0.0.0.0", port=PORT)


# ---------------------------------------------------------------------------
# Bot handlers
# ---------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send banner + welcome message when /start is received."""
    user = update.effective_user
    first_name = user.first_name if user else ""

    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_URL),
         InlineKeyboardButton("💬 Join Group", url=GROUP_URL)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    caption = WELCOME_TEXT.format(name=first_name, url=CHANNEL_URL)

    if os.path.exists(BANNER_PATH):
        with open(BANNER_PATH, "rb") as banner:
            await update.message.reply_photo(
                photo=banner,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=reply_markup,
            )
    else:
        await update.message.reply_text(
            caption,
            parse_mode="Markdown",
            reply_markup=reply_markup,
            disable_web_page_preview=False,
        )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simple /help command."""
    await update.message.reply_text(
        "🤖 *KING MULTIVERSE Bot*\n\n"
        "Commands:\n"
        "/start - Welcome message\n"
        "/help - This message\n\n"
        f"Channel: {CHANNEL_URL}",
        parse_mode="Markdown",
    )


async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reply to any unrecognized message."""
    await update.message.reply_text(
        "I didn't understand that. Send /start to begin or visit "
        f"{CHANNEL_URL}"
    )


def main():
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN environment variable is not set!")
        print("Set it on Render > Environment > Add Environment Variable")
        return

    # Start Flask keep-alive in background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"Flask keep-alive running on port {PORT}")

    # Build and run the bot
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback))

    logger.info(f"✅ @{BOT_USERNAME} is running...")
    logger.info(f"   Channel: {CHANNEL_URL}")
    logger.info(f"   Group: {GROUP_URL}")
    app.run_polling()


if __name__ == "__main__":
    main()
