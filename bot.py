"""
KING MULTIVERSE Telegram Bot
============================
Bot: @KING_Multiverse_Robot

Uses Pyrogram with:
  - BOT_TOKEN  -> Bot mode (handles /start, /help, buttons, auth key)
  - SESSION_STRING -> User mode (forwards messages from source channels to bot)
  - API_ID, API_HASH -> from my.telegram.org
  - AUTH_KEY_URL -> link for getting auth key

Deploy on Render:
  - Set env vars: BOT_TOKEN, API_ID, API_HASH, SESSION_STRING, AUTH_KEY_URL
  - Start command: python bot.py
"""

import os
import asyncio
import logging
import threading
from flask import Flask, jsonify
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# ---------------------------------------------------------------------------
# CONFIG — all secrets come from environment variables (set on Render)
# ---------------------------------------------------------------------------
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
AUTH_KEY_URL = os.environ.get("AUTH_KEY_URL", "https://t.me/ModAppsKing")

BOT_USERNAME = "KING_Multiverse_Robot"
BANNER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Tg_Banner.jpg")
CHANNEL_URL = "https://t.me/ModAppsKing"
GROUP_URL = "https://t.me/ANONYMOUS_GROUP_KING"
PORT = int(os.environ.get("PORT", 10000))

# Source channel/chat IDs from where messages should be forwarded to the bot
# Format: list of chat IDs (integers). You can add more.
# Example: -1001234567890
SOURCE_CHAT_IDS = []
# ---------------------------------------------------------------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "👋 Hello {name}!\n\n"
    "Welcome to **KING MULTIVERSE** Bot.\n\n"
    "🚀 For the best experience, premium mod apps, games, tools "
    "and fast updates please use our official Channel:\n\n"
    "🌐 {url}\n\n"
    "Enjoy premium apps for free and keep modding! 🚀"
)

AUTH_KEY_TEXT = (
    "🔒 **Auth Key Required**\n\n"
    "To continue, generate your Auth Key using the link below:\n\n"
    "🔗 [Click Here to Get Auth Key]({url})\n\n"
    "⚠️ **Important:** Keep your Auth Key private and do not share it with anyone.\n\n"
    "💡 If the link expires, simply request a new one from the app."
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
            "session_string": "set" if SESSION_STRING else "not set",
            "auth_key_url": AUTH_KEY_URL,
        }
    )


@app_flask.route("/health")
def health():
    return jsonify({"status": "ok"})


def run_flask():
    app_flask.run(host="0.0.0.0", port=PORT)


# ---------------------------------------------------------------------------
# Pyrogram Client — Bot mode + User session
# ---------------------------------------------------------------------------
bot = Client(
    "king_multiverse_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
)

# User client for forwarding messages (uses SESSION_STRING)
user = Client(
    "king_multiverse_user",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True,
) if SESSION_STRING else None


# ---------------------------------------------------------------------------
# Helper — main inline keyboard (Join Channel, Join Group, How To Get Auth Key, Close)
# ---------------------------------------------------------------------------
def main_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📢 Join Channel", url=CHANNEL_URL),
                InlineKeyboardButton("💬 Join Group", url=GROUP_URL),
            ],
            [
                InlineKeyboardButton("🔑 How To Get Auth Key", url=AUTH_KEY_URL),
                InlineKeyboardButton("🔒 Close", callback_data="close"),
            ],
        ]
    )


# ---------------------------------------------------------------------------
# Bot handlers
# ---------------------------------------------------------------------------
@bot.on_message(filters.command("start"))
async def start_handler(client: Client, message: Message):
    """Send banner + welcome message + auth key message when /start is received."""
    user_info = await client.get_users(message.from_user.id)
    first_name = user_info.first_name if user_info else ""

    # 1. Send banner with welcome caption
    caption = WELCOME_TEXT.format(name=first_name, url=CHANNEL_URL)

    if os.path.exists(BANNER_PATH):
        await message.reply_photo(
            photo=BANNER_PATH,
            caption=caption,
            reply_markup=main_keyboard(),
        )
    else:
        await message.reply_text(
            caption,
            reply_markup=main_keyboard(),
            disable_web_page_preview=False,
        )

    # 2. Send Auth Key required message
    auth_msg = AUTH_KEY_TEXT.format(url=AUTH_KEY_URL)
    await message.reply_text(
        auth_msg,
        reply_markup=main_keyboard(),
        disable_web_page_preview=False,
    )


@bot.on_callback_query(filters.regex("close"))
async def close_handler(client: Client, callback_query):
    """Handle Close button — delete the message."""
    await callback_query.message.delete()
    await callback_query.answer("🔒 Closed!")


@bot.on_message(filters.command("help"))
async def help_handler(client: Client, message: Message):
    """Simple /help command."""
    await message.reply_text(
        "🤖 **KING MULTIVERSE Bot**\n\n"
        "Commands:\n"
        "/start - Welcome + Auth Key\n"
        "/help - This message\n"
        "/status - Bot status\n\n"
        f"Channel: {CHANNEL_URL}",
        reply_markup=main_keyboard(),
    )


@bot.on_message(filters.command("status"))
async def status_handler(client: Client, message: Message):
    """Check bot and user session status."""
    status_text = f"🤖 Bot: **Online**\n"

    if user:
        try:
            me = await user.get_me()
            status_text += f"👤 User Session: **Active** ({me.first_name})\n"
        except Exception:
            status_text += "👤 User Session: **Error**\n"
    else:
        status_text += "👤 User Session: **Not configured**\n"

    status_text += f"📡 API_ID: `{API_ID}`\n"
    status_text += f"🔗 Channel: {CHANNEL_URL}\n"
    status_text += f"🔑 Auth Key URL: {AUTH_KEY_URL}"

    await message.reply_text(status_text)


@bot.on_message(filters.text & ~filters.command(["start", "help", "status"]))
async def fallback_handler(client: Client, message: Message):
    """Reply to any unrecognized message."""
    await message.reply_text(
        "I didn't understand that. Send /start to begin or visit "
        f"{CHANNEL_URL}",
        reply_markup=main_keyboard(),
    )


# ---------------------------------------------------------------------------
# User session — Forward messages from source channels to bot
# ---------------------------------------------------------------------------
if user:
    @user.on_message()
    async def forward_handler(client: Client, message: Message):
        """Forward incoming messages from source chats to the bot."""
        try:
            # If SOURCE_CHAT_IDS is empty, forward from all chats
            if not SOURCE_CHAT_IDS or message.chat.id in SOURCE_CHAT_IDS:
                await message.forward(chat_id=BOT_TOKEN)
                logger.info(f"Forwarded message from chat {message.chat.id}")
        except Exception as e:
            logger.error(f"Forward error: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN environment variable is not set!")
        print("Set it on Render > Environment > Add Environment Variable")
        return

    if not API_ID or not API_HASH:
        print("ERROR: API_ID and API_HASH environment variables are not set!")
        print("Get them from https://my.telegram.org")
        return

    # Start user session (for message forwarding)
    if user:
        try:
            await user.start()
            me = await user.get_me()
            logger.info(f"✅ User session started: {me.first_name} (@{me.username})")
        except Exception as e:
            logger.error(f"Failed to start user session: {e}")
    else:
        logger.warning("⚠️ SESSION_STRING not set — message forwarding disabled!")

    # Start bot
    await bot.start()
    bot_info = await bot.get_me()
    logger.info(f"✅ Bot started: @{bot_info.username}")
    logger.info(f"   Channel: {CHANNEL_URL}")
    logger.info(f"   Group: {GROUP_URL}")
    logger.info(f"   Auth Key URL: {AUTH_KEY_URL}")

    # Keep running
    await asyncio.Event().wait()


if __name__ == "__main__":
    # Start Flask keep-alive in background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"Flask keep-alive running on port {PORT}")

    # Run the Pyrogram clients
    asyncio.run(main())
