"""
KING MULTIVERSE Telegram Bot — Clone of @AS_Multiverse_Robot
=============================================================
Bot: @KING_Multiverse_Robot

ARCHITECTURE (Proxy/Mirror Bot):
  User → Our Bot → (SESSION_STRING) → TARGET BOT (@AS_Multiverse_Robot)
                                              ↓
  User ← Our Bot ← (copied response) ← Auth Key message + fresh arolinks URL

- Our bot forwards everything to the TARGET bot via user session
- TARGET bot's responses (with dynamic arolinks links) are copied to the user
- Buttons are mirrored — clicking sends the same action to TARGET bot
- Every /start gets a FRESH arolinks URL from the TARGET bot

Deploy on Render:
  - Set env vars: BOT_TOKEN, API_ID, API_HASH, SESSION_STRING, TARGET_BOT
  - Start command: python bot.py
"""

import os
import asyncio
import logging
import threading
import re
import urllib.parse
from flask import Flask, jsonify
from telethon import TelegramClient, Button, events
from telethon.sessions import StringSession

# ---------------------------------------------------------------------------
# CONFIG — all secrets come from environment variables (set on Render)
# ---------------------------------------------------------------------------
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
TARGET_BOT = os.environ.get("TARGET_BOT", "@AS_Multiverse_Robot")

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
            "target": TARGET_BOT,
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
# Telethon Clients
# ---------------------------------------------------------------------------
# Bot client — users interact with this (our bot)
bot = TelegramClient("king_bot", API_ID, API_HASH)

# User client — talks to the TARGET bot (original AS Multiverse)
user = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH) if SESSION_STRING else None


# ---------------------------------------------------------------------------
# Shared state — communication between bot handlers and target responses
# ---------------------------------------------------------------------------
captured_msg = None
response_event = asyncio.Event()
last_target_msg = None


# ---------------------------------------------------------------------------
# Target bot response handler — captures messages from TARGET bot
# ---------------------------------------------------------------------------
if user:
    @user.on(events.NewMessage(chats=TARGET_BOT))
    @user.on(events.MessageEdited(chats=TARGET_BOT))
    async def target_response_handler(event):
        """Capture incoming messages from the TARGET bot."""
        global captured_msg, response_event

        if event.out:
            return

        text = event.message.text or ""

        # Skip loading/fetching messages
        if "fetching" in text.lower() or "loading" in text.lower():
            return

        captured_msg = event.message
        response_event.set()


# ---------------------------------------------------------------------------
# Helpers — copy target bot's buttons to our bot's format
# ---------------------------------------------------------------------------
def copy_buttons(telethon_msg):
    """Copy inline buttons from target bot's message."""
    if not telethon_msg or not telethon_msg.buttons:
        return None

    keyboard = []
    for row in telethon_msg.buttons:
        row_buttons = []
        for btn in row:
            if hasattr(btn, "url") and btn.url:
                # URL button — keep the same URL (arolinks etc.)
                row_buttons.append(Button.url(btn.text, btn.url))
            elif hasattr(btn, "data") and btn.data:
                # Callback button — map to our own callback
                row_buttons.append(Button.inline(btn.text, data=f"act_{btn.text[:60]}"))
        if row_buttons:
            keyboard.append(row_buttons)
    return keyboard


# ---------------------------------------------------------------------------
# Core — send message to TARGET bot and wait for response
# ---------------------------------------------------------------------------
async def send_to_target(text):
    """Send a message to the TARGET bot and capture its response."""
    global captured_msg, response_event

    if not user:
        return None

    response_event.clear()
    captured_msg = None

    await user.send_message(TARGET_BOT, text)

    try:
        await asyncio.wait_for(response_event.wait(), timeout=30.0)
        return captured_msg
    except asyncio.TimeoutError:
        return None


async def click_target_button(row_idx, col_idx):
    """Click a button on the TARGET bot's last message."""
    global last_target_msg, captured_msg, response_event

    if not last_target_msg or not last_target_msg.buttons:
        return None

    try:
        response_event.clear()
        captured_msg = None

        btn = last_target_msg.buttons[row_idx][col_idx]

        if hasattr(btn, "url") and btn.url:
            # URL button with start parameter → send /start PARAM to target
            parsed = urllib.parse.urlparse(btn.url)
            params = urllib.parse.parse_qs(parsed.query)
            if "start" in params:
                start_value = params["start"][0]
                await user.send_message(TARGET_BOT, f"/start {start_value}")
                await asyncio.wait_for(response_event.wait(), timeout=30.0)
                return captured_msg
        elif hasattr(btn, "data") and btn.data:
            # Callback button → click it on target
            await btn.click()
            await asyncio.wait_for(response_event.wait(), timeout=30.0)
            return captured_msg
        else:
            await user.send_message(TARGET_BOT, "/start")
            await asyncio.wait_for(response_event.wait(), timeout=30.0)
            return captured_msg

        return None
    except asyncio.TimeoutError:
        return None
    except Exception as e:
        logger.error(f"Button click error: {e}")
        return None


# ---------------------------------------------------------------------------
# Forward target's response to user
# ---------------------------------------------------------------------------
async def forward_response(event, target_msg, status_msg=None):
    """Send the TARGET bot's response to the user."""
    global last_target_msg

    if status_msg:
        try:
            await status_msg.delete()
        except Exception:
            pass

    if target_msg:
        last_target_msg = target_msg
        buttons = copy_buttons(target_msg)
        text = target_msg.text or "✅ Done"

        await event.reply(text, buttons=buttons, link_preview=False)
    else:
        await event.reply("❌ Target bot not responding. Try /start again.")


# ---------------------------------------------------------------------------
# Our Bot handlers — proxy everything to TARGET bot
# ---------------------------------------------------------------------------
@bot.on(events.NewMessage(pattern="/start"))
async def start_handler(event):
    """User sends /start → forward to TARGET bot → send response back."""
    text = event.raw_text.strip()

    status = await event.reply("⏳ Processing...")

    # Forward /start (with or without param) to TARGET bot
    target_response = await send_to_target(text)

    await forward_response(event, target_response, status)


@bot.on(events.NewMessage(pattern="/help"))
async def help_handler(event):
    """User sends /help → forward to TARGET bot."""
    status = await event.reply("⏳ Processing...")
    target_response = await send_to_target("/start")
    await forward_response(event, target_response, status)


@bot.on(events.NewMessage(pattern="/status"))
async def status_handler(event):
    """Check bot status."""
    status_text = "🤖 Bot: **Online**\n"

    if user:
        try:
            me = await user.get_me()
            status_text += f"👤 User Session: **Active** ({me.first_name})\n"
            status_text += f"🎯 Target Bot: `{TARGET_BOT}`\n"
        except Exception:
            status_text += "👤 User Session: **Error**\n"
    else:
        status_text += "👤 User Session: **Not configured**\n"

    status_text += f"🔗 Channel: {CHANNEL_URL}"

    await event.reply(status_text)


@bot.on(events.CallbackQuery(data=re.compile(rb"^act_")))
async def callback_handler(event):
    """User clicks a button → find matching button on TARGET bot → click it."""
    global last_target_msg

    try:
        await event.answer("Processing...")
    except Exception:
        pass

    # Extract button text from our callback data
    button_text = event.data.decode("utf-8")[4:]  # Remove "act_" prefix

    status = await event.reply("⏳ Processing...")

    button_found = False
    if last_target_msg and last_target_msg.buttons:
        for row_idx, row in enumerate(last_target_msg.buttons):
            for col_idx, btn in enumerate(row):
                if btn.text == button_text:
                    button_found = True

                    # Click the matching button on TARGET bot
                    target_response = await click_target_button(row_idx, col_idx)
                    await forward_response(event, target_response, status)
                    return

    if not button_found:
        try:
            await status.delete()
        except Exception:
            pass
        await event.reply("❌ Button expired. Send /start again.")


@bot.on(events.NewMessage(func=lambda e: True))
async def text_handler(event):
    """Any other text → forward to TARGET bot (search etc.)."""
    if event.raw_text.startswith("/"):
        return  # Skip commands (handled above)

    status = await event.reply("⏳ Processing...")

    # Forward user's text to TARGET bot
    target_response = await send_to_target(event.raw_text)

    await forward_response(event, target_response, status)


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

    # Start user session (proxy connection to TARGET bot)
    if user:
        try:
            await user.start()
            me = await user.get_me()
            logger.info(f"✅ User session started: {me.first_name} (@{me.username})")
            logger.info(f"🎯 Target bot: {TARGET_BOT}")
        except Exception as e:
            logger.error(f"Failed to start user session: {e}")
            return
    else:
        logger.error("⚠️ SESSION_STRING not set — bot cannot work without it!")
        return

    # Start bot
    await bot.start(bot_token=BOT_TOKEN)
    me = await bot.get_me()
    logger.info(f"✅ Bot started: @{me.username}")
    logger.info(f"   Proxy target: {TARGET_BOT}")
    logger.info(f"   Channel: {CHANNEL_URL}")

    # Keep running
    await bot.run_until_disconnected()


if __name__ == "__main__":
    # Start Flask keep-alive in background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"Flask keep-alive running on port {PORT}")

    # Run the Telethon clients
    asyncio.run(main())
