"""
KING MULTIVERSE Telegram Bot — Clone of @AS_Multiverserobot
=============================================================
Bot: @KING_Multiverse_Robot

ARCHITECTURE (Proxy/Mirror Bot):
  User → Our Bot → (SESSION_STRING) → TARGET BOT (@AS_Multiverserobot)
                                              ↓
  User ← Our Bot ← (copied response) ← Auth Key message + fresh arolinks URL

Features:
- Forwards ALL messages to TARGET bot via user session
- Copies responses (text + media + buttons) to user
- Replaces AS Multiverse links with OUR links
- 3-tier media delivery: FAST (user session direct) → MEDIUM (bot w/ ref) → SLOW (download+upload)
- Long timeout (3 min) for video responses
- Every /start gets a FRESH arolinks URL from TARGET bot

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
TARGET_BOT = os.environ.get("TARGET_BOT", "@AS_Multiverserobot")

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
# Shared state
# ---------------------------------------------------------------------------
captured_msg = None
response_event = asyncio.Event()
last_target_msg = None


# ---------------------------------------------------------------------------
# Link replacement — replace AS Multiverse URLs with ours
# ---------------------------------------------------------------------------
def replace_url(url):
    """Replace AS Multiverse URLs with our bot's URLs."""
    if not url:
        return url
    # Replace bot username in deep links (t.me/AS_Multiverserobot → t.me/KING_Multiverse_Robot)
    url = url.replace("AS_Multiverserobot", BOT_USERNAME)
    # Replace website with our channel
    url = url.replace("https://asmultiverse.com", CHANNEL_URL)
    url = url.replace("http://asmultiverse.com", CHANNEL_URL)
    url = url.replace("asmultiverse.com", "t.me/ModAppsKing")
    return url


def replace_text_links(text):
    """Replace AS Multiverse links in message text."""
    if not text:
        return text
    # Replace website links
    text = text.replace("https://asmultiverse.com", CHANNEL_URL)
    text = text.replace("http://asmultiverse.com", CHANNEL_URL)
    text = text.replace("asmultiverse.com", "t.me/ModAppsKing")
    # Replace bot deep links
    text = text.replace("t.me/AS_Multiverserobot", f"t.me/{BOT_USERNAME}")
    text = text.replace("@AS_Multiverserobot", f"@{BOT_USERNAME}")
    return text


# ---------------------------------------------------------------------------
# Target bot response handler
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
# Helpers — copy target bot's buttons with URL replacement
# ---------------------------------------------------------------------------
def copy_buttons(telethon_msg):
    """Copy inline buttons from target bot's message, replacing URLs."""
    if not telethon_msg or not telethon_msg.buttons:
        return None

    keyboard = []
    for row in telethon_msg.buttons:
        row_buttons = []
        for btn in row:
            btn_text = btn.text.strip()

            # Replace Join Channel / Join Group buttons with OUR links
            if "join channel" in btn_text.lower():
                row_buttons.append(Button.url(btn_text, CHANNEL_URL))
                continue
            elif "join group" in btn_text.lower():
                row_buttons.append(Button.url(btn_text, GROUP_URL))
                continue

            if hasattr(btn, "url") and btn.url:
                # URL button — replace AS Multiverse URLs with ours
                new_url = replace_url(btn.url)
                row_buttons.append(Button.url(btn_text, new_url))
            elif hasattr(btn, "data") and btn.data:
                # Callback button — map to our own callback
                row_buttons.append(Button.inline(btn_text, data=f"act_{btn_text[:60]}"))
        if row_buttons:
            keyboard.append(row_buttons)
    return keyboard


# ---------------------------------------------------------------------------
# Core — send message to TARGET bot and wait for response
# ---------------------------------------------------------------------------
async def send_to_target(text, timeout=30.0):
    """Send a message to the TARGET bot and capture its response.

    Use longer timeout for quality requests (videos take time).
    """
    global captured_msg, response_event

    if not user:
        logger.error("User client not available!")
        return None

    response_event.clear()
    captured_msg = None

    try:
        await user.send_message(TARGET_BOT, text)
        logger.info(f"Sent to TARGET bot: {text[:50]}")
    except Exception as e:
        logger.error(f"Failed to send to TARGET bot: {e}")
        return None

    try:
        await asyncio.wait_for(response_event.wait(), timeout=timeout)
        logger.info(f"Got response from TARGET bot: {(captured_msg.text or '')[:50]}")
        return captured_msg
    except asyncio.TimeoutError:
        logger.error(f"Timeout ({timeout}s) waiting for TARGET bot response!")
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
                await asyncio.wait_for(response_event.wait(), timeout=180.0)
                return captured_msg
            # URL button without start param — just forward the URL to user
            return None
        elif hasattr(btn, "data") and btn.data:
            # Callback button → click it on target
            await btn.click()
            await asyncio.wait_for(response_event.wait(), timeout=180.0)
            return captured_msg
        else:
            await user.send_message(TARGET_BOT, "/start")
            await asyncio.wait_for(response_event.wait(), timeout=180.0)
            return captured_msg

        return None
    except asyncio.TimeoutError:
        logger.error("Timeout waiting for button response!")
        return None
    except Exception as e:
        logger.error(f"Button click error: {e}")
        return None


# ---------------------------------------------------------------------------
# Forward target's response to user — 3-tier media delivery
# ---------------------------------------------------------------------------
async def forward_response(event, target_msg, status_msg=None):
    """Send the TARGET bot's response to the user — text + media + buttons.

    Media delivery strategy (fastest to slowest):
    1. FAST: user.send_file() with file reference → instant, no download
    2. MEDIUM: bot sends with media reference
    3. SLOW: download to disk then re-upload
    """
    global last_target_msg

    if status_msg:
        try:
            await status_msg.delete()
        except Exception:
            pass

    if target_msg:
        last_target_msg = target_msg
        buttons = copy_buttons(target_msg)
        text = replace_text_links(target_msg.text or "")

        # Check if the message has media (photo, video, document)
        if target_msg.media:
            # FAST PATH: Send media directly via USER session
            # This uses the file reference — no download/re-upload needed!
            # Telegram just copies the file to the user's chat. INSTANT!
            try:
                logger.info(f"Sending media via USER session (fast): {type(target_msg.media).__name__}")
                await user.send_file(
                    event.chat_id,  # End user's chat ID
                    file=target_msg.media,
                    caption=text or None,
                    supports_streaming=True,
                )
                # Send buttons separately via bot (user session can't send inline buttons)
                if buttons:
                    await event.reply("👆 Your file is above!", buttons=buttons, link_preview=False)
                else:
                    await event.reply("✅ Done", link_preview=False)
                return
            except Exception as e:
                logger.error(f"User session send failed: {e}")
                # Fallback: try sending via BOT with media reference

            # MEDIUM PATH: Send via BOT with media reference
            try:
                logger.info("Trying BOT send with media reference...")
                await event.reply(
                    text or " ",
                    file=target_msg.media,
                    buttons=buttons,
                    link_preview=False,
                )
                return
            except Exception as e:
                logger.error(f"Bot media send failed: {e}")

            # SLOW PATH: Download & re-upload via bot
            try:
                logger.info("Trying download & re-upload (slow)...")
                media_path = await target_msg.download_media()
                if media_path:
                    await event.reply(
                        text or " ",
                        file=media_path,
                        buttons=buttons,
                        link_preview=False,
                    )
                    # Cleanup
                    try:
                        os.remove(media_path)
                    except Exception:
                        pass
                    return
            except Exception as e2:
                logger.error(f"Download & re-upload failed: {e2}")

        # Text only (no media or media failed)
        await event.reply(text or "✅ Done", buttons=buttons, link_preview=False)
    else:
        await event.reply("❌ Target bot not responding. Try /start again.")


# ---------------------------------------------------------------------------
# Our Bot handlers — proxy everything to TARGET bot
# ---------------------------------------------------------------------------
@bot.on(events.NewMessage(pattern="/start"))
async def start_handler(event):
    """User sends /start → forward to TARGET bot → send response back."""
    text = event.raw_text.strip()

    # Check if this is a quality request (e.g. /start PARAM_480)
    # Quality requests return videos — need much longer timeout
    is_quality_request = False
    parts = text.split(" ", 1)
    if len(parts) > 1:
        param = parts[1].strip().lower()
        for q in ["_720", "_480", "_360", "_240", "720p", "480p", "360p", "240p"]:
            if q in param:
                is_quality_request = True
                break

    if is_quality_request:
        status = await event.reply("⏳ Fetching video... This may take a moment.")
        timeout = 180.0  # 3 minutes for video responses
    else:
        status = await event.reply("⏳ Processing...")
        timeout = 30.0

    try:
        # Forward /start (with or without param) to TARGET bot
        target_response = await send_to_target(text, timeout=timeout)
        await forward_response(event, target_response, status)
    except Exception as e:
        logger.error(f"Error in start handler: {e}")
        try:
            await status.delete()
        except Exception:
            pass
        await event.reply("❌ Something went wrong. Try /start again.")


@bot.on(events.NewMessage(pattern="/help"))
async def help_handler(event):
    """User sends /help → forward to TARGET bot."""
    status = await event.reply("⏳ Processing...")
    try:
        target_response = await send_to_target("/start")
        await forward_response(event, target_response, status)
    except Exception as e:
        logger.error(f"Error in help handler: {e}")
        await forward_response(event, None, status)


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

    # Check if this is a quality button (720p, 480p etc.) — videos take time
    is_quality = any(q in button_text.lower() for q in ["720", "480", "360", "240"])
    if is_quality:
        status = await event.reply("⏳ Fetching video... This may take a moment.")
    else:
        status = await event.reply("⏳ Processing...")

    button_found = False
    if last_target_msg and last_target_msg.buttons:
        for row_idx, row in enumerate(last_target_msg.buttons):
            for col_idx, btn in enumerate(row):
                if btn.text.strip() == button_text:
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

    try:
        # Forward user's text to TARGET bot
        target_response = await send_to_target(event.raw_text)
        await forward_response(event, target_response, status)
    except Exception as e:
        logger.error(f"Error in text handler: {e}")
        await forward_response(event, None, status)


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

            # Resolve TARGET_BOT entity
            try:
                target_entity = await user.get_entity(TARGET_BOT)
                logger.info(f"🎯 Target bot resolved: {getattr(target_entity, 'title', TARGET_BOT)}")
            except Exception as e:
                logger.error(f"❌ Could not resolve TARGET_BOT '{TARGET_BOT}': {e}")
                logger.error("   Make sure the username is correct!")
                return

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
