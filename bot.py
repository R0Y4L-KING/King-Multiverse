"""
KING MULTIVERSE Telegram Bot
============================
Bot: @KING_Multiverse_Robot

Uses Telethon with:
  - BOT_TOKEN  -> Bot mode (handles /start, /help, buttons)
  - SESSION_STRING -> User mode (forwards messages from source channels to bot)
  - API_ID, API_HASH -> from my.telegram.org

Deploy on Render:
  - Set env vars: BOT_TOKEN, API_ID, API_HASH, SESSION_STRING
  - Start command: python bot.py
"""

import os
import asyncio
import logging
import threading
from flask import Flask, jsonify
from telethon import TelegramClient, Button
from telethon.events import NewMessage, CallbackQuery

# ---------------------------------------------------------------------------
# CONFIG — all secrets come from environment variables (set on Render)
# ---------------------------------------------------------------------------
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")

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
        }
    )


@app_flask.route("/health")
def health():
    return jsonify({"status": "ok"})


def run_flask():
    app_flask.run(host="0.0.0.0", port=PORT)


# ---------------------------------------------------------------------------
# Telethon Clients — Bot mode + User session
# ---------------------------------------------------------------------------
bot = TelegramClient("king_bot", API_ID, API_HASH)
user = TelegramClient("king_user", API_ID, API_HASH, session_string=SESSION_STRING) if SESSION_STRING else None


# ---------------------------------------------------------------------------
# Helper — main inline keyboard
# ---------------------------------------------------------------------------
def main_keyboard():
    return [
        [
            Button.url("📢 Join Channel", CHANNEL_URL),
            Button.url("💬 Join Group", GROUP_URL),
        ],
        [
            Button.inline("🔒 Close", data="close"),
        ],
    ]


# ---------------------------------------------------------------------------
# Bot handlers
# ---------------------------------------------------------------------------
@bot.on(NewMessage(pattern="/start"))
async def start_handler(event):
    """Send banner + welcome message when /start is received."""
    sender = await event.get_sender()
    first_name = sender.first_name if sender else ""

    caption = WELCOME_TEXT.format(name=first_name, url=CHANNEL_URL)

    if os.path.exists(BANNER_PATH):
        await event.reply(
            caption,
            file=BANNER_PATH,
            buttons=main_keyboard(),
            link_preview=False,
        )
    else:
        await event.reply(
            caption,
            buttons=main_keyboard(),
            link_preview=False,
        )


@bot.on(CallbackQuery(data="close"))
async def close_handler(event):
    """Handle Close button — delete the message."""
    await event.delete()
    await event.answer("🔒 Closed!")


@bot.on(NewMessage(pattern="/help"))
async def help_handler(event):
    """Simple /help command."""
    await event.reply(
        "🤖 **KING MULTIVERSE Bot**\n\n"
        "Commands:\n"
        "/start - Welcome message\n"
        "/help - This message\n"
        "/status - Bot status\n\n"
        f"Channel: {CHANNEL_URL}",
        buttons=main_keyboard(),
        link_preview=False,
    )


@bot.on(NewMessage(pattern="/status"))
async def status_handler(event):
    """Check bot and user session status."""
    status_text = "🤖 Bot: **Online**\n"

    if user:
        try:
            me = await user.get_me()
            status_text += f"👤 User Session: **Active** ({me.first_name})\n"
        except Exception:
            status_text += "👤 User Session: **Error**\n"
    else:
        status_text += "👤 User Session: **Not configured**\n"

    status_text += f"📡 API_ID: `{API_ID}`\n"
    status_text += f"🔗 Channel: {CHANNEL_URL}"

    await event.reply(status_text)


# ---------------------------------------------------------------------------
# User session — Forward messages from source channels to bot
# ---------------------------------------------------------------------------
if user:
    @user.on(NewMessage())
    async def forward_handler(event):
        """Forward incoming messages from source chats to the bot."""
        try:
            if not SOURCE_CHAT_IDS or event.chat_id in SOURCE_CHAT_IDS:
                await event.forward_to(bot)
                logger.info(f"Forwarded message from chat {event.chat_id}")
        except Exception as e:
            logger.error(f"Forward error: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN environment variable is not set!")
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
    await bot.start(bot_token=BOT_TOKEN)
    me = await bot.get_me()
    logger.info(f"✅ Bot started: @{me.username}")
    logger.info(f"   Channel: {CHANNEL_URL}")
    logger.info(f"   Group: {GROUP_URL}")

    # Keep running
    await bot.run_until_disconnected()


if __name__ == "__main__":
    # Start Flask keep-alive in background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"Flask keep-alive running on port {PORT}")

    # Run the Telethon clients
    asyncio.run(main())
