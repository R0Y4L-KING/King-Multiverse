"""
KING MULTIVERSE Telegram Bot — Clone of @AS_Multiverserobot
=============================================================
Bot: @KING_Multiverse_Robot

ARCHITECTURE (Proxy/Mirror Bot):
  User → Our Bot → (SESSION_STRING) → TARGET BOT (@AS_Multiverserobot)
                                              ↓
  User ← Our Bot ← (copied response) ← Auth Key message + fresh arolinks URL

Deploy on Render:
  - Set env vars: BOT_TOKEN, API_ID, API_HASH, SESSION_STRING, TARGET_BOT
  - Start command: python bot.py
"""

import os
import time
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
# Optional: a private channel/group where BOTH the user session and the bot
# are members. When set, video delivery is instant regardless of size —
# see relay_via_log_chat() for why this fixes the size-dependent delay.
_log_chat_raw = os.environ.get("LOG_CHAT_ID", "").strip()
try:
    LOG_CHAT_ID = int(_log_chat_raw) if _log_chat_raw else None
except ValueError:
    LOG_CHAT_ID = _log_chat_raw or None  # allow @username as a fallback

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
bot = TelegramClient("king_bot", API_ID, API_HASH)
user = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH) if SESSION_STRING else None


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------
captured_msg = None
response_event = asyncio.Event()
last_target_msg = None


# ---------------------------------------------------------------------------
# Link replacement — replace ALL AS Multiverse branding with ours
# ---------------------------------------------------------------------------
def replace_url(url):
    """Replace AS Multiverse URLs with our bot's URLs."""
    if not url:
        return url
    url = url.replace("AS_Multiverserobot", BOT_USERNAME)
    url = url.replace("https://asmultiverse.com", CHANNEL_URL)
    url = url.replace("http://asmultiverse.com", CHANNEL_URL)
    url = url.replace("asmultiverse.com", "t.me/ModAppsKing")
    url = url.replace("t.me/heheAnyQuestion", "t.me/ModAppsKing")
    url = url.replace("https://t.me/heheAnyQuestion", CHANNEL_URL)
    return url


def replace_text_links(text):
    """Replace AS Multiverse links and branding in message text."""
    if not text:
        return text
    text = text.replace("https://asmultiverse.com", CHANNEL_URL)
    text = text.replace("http://asmultiverse.com", CHANNEL_URL)
    text = text.replace("asmultiverse.com", "t.me/ModAppsKing")
    text = text.replace("t.me/AS_Multiverserobot", f"t.me/{BOT_USERNAME}")
    text = text.replace("@AS_Multiverserobot", f"@{BOT_USERNAME}")
    text = text.replace("AS MULTIVERSE", "KING MULTIVERSE")
    text = text.replace("AS Multiverse", "KING MULTIVERSE")
    # Replace MadXABhi branding with MODAPPSKING — regex-based because the
    # source bot swaps in unicode look-alike characters and decorative
    # brackets (e.g. "【✳MAD乂ABHI✳】") specifically to dodge plain .replace()
    # matching. This matches M-A-D-<anything>-A-B-H-I regardless of what
    # symbol/spacing sits in the gaps, then cleans up any decorative
    # brackets left wrapping it.
    text = text.replace("t.me/heheAnyQuestion", "t.me/ModAppsKing")
    text = re.sub(
        r'(?<![A-Za-z])M.{0,2}A.{0,2}D.{0,3}A.{0,2}B.{0,2}H.{0,2}I(?![A-Za-z])',
        "MODAPPSKING",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r'[\[\(\{【<][\s✳✴🌟☀~\-_*※]*MODAPPSKING[\s✳✴🌟☀~\-_*※]*[\]\)\}】>]',
        "MODAPPSKING",
        text,
    )
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

            if "join channel" in btn_text.lower():
                row_buttons.append(Button.url(btn_text, CHANNEL_URL))
                continue
            elif "join group" in btn_text.lower():
                row_buttons.append(Button.url(btn_text, GROUP_URL))
                continue

            if hasattr(btn, "url") and btn.url:
                new_url = replace_url(btn.url)
                row_buttons.append(Button.url(btn_text, new_url))
            elif hasattr(btn, "data") and btn.data:
                row_buttons.append(Button.inline(btn_text, data=f"act_{btn_text[:60]}"))
        if row_buttons:
            keyboard.append(row_buttons)
    return keyboard


# ---------------------------------------------------------------------------
# Core — send message to TARGET bot and wait for response
# ---------------------------------------------------------------------------
async def send_to_target(text, timeout=30.0):
    """Send a message to the TARGET bot and capture its response."""
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
            parsed = urllib.parse.urlparse(btn.url)
            params = urllib.parse.parse_qs(parsed.query)
            if "start" in params:
                start_value = params["start"][0]
                await user.send_message(TARGET_BOT, f"/start {start_value}")
                await asyncio.wait_for(response_event.wait(), timeout=180.0)
                return captured_msg
            return None
        elif hasattr(btn, "data") and btn.data:
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
# Throttled progress callback — shows live % during download/upload instead
# of the bot looking frozen while a big video is transferred.
# ---------------------------------------------------------------------------
def _make_progress_cb(status_msg, label):
    state = {"pct": -100, "t": 0.0}

    async def cb(current, total):
        if not status_msg or not total:
            return
        pct = int(current * 100 / total)
        now = time.time()
        # Only edit every ~15% or ~3s, and always on completion, to avoid
        # Telegram edit-rate limits on big files with many chunks.
        if pct < 100 and pct - state["pct"] < 15 and now - state["t"] < 3:
            return
        state["pct"], state["t"] = pct, now
        try:
            await status_msg.edit(f"{label} {pct}%")
        except Exception:
            pass

    return cb


# ---------------------------------------------------------------------------
# Forward target's response to user — smart media handling
# ---------------------------------------------------------------------------
async def forward_response(event, target_msg, status_msg=None):
    """Send the TARGET bot's response to the user — text + media + buttons."""
    global last_target_msg

    async def _clear_status():
        # Was previously called unconditionally at the top of this function,
        # which deleted status_msg before video's Strategy 3 ever got a
        # chance to edit it for progress %. Now called explicitly at each
        # point where we're done with it (or don't need it, e.g. photo).
        if status_msg:
            try:
                await status_msg.delete()
            except Exception:
                pass

    if target_msg:
        last_target_msg = target_msg
        buttons = copy_buttons(target_msg)
        text = replace_text_links(target_msg.text or "")

        if target_msg.media:
            from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument

            is_photo = isinstance(target_msg.media, MessageMediaPhoto)
            is_video = False

            if isinstance(target_msg.media, MessageMediaDocument):
                doc = target_msg.media.document
                if doc and doc.mime_type and "video" in doc.mime_type:
                    is_video = True

            if is_photo:
                # PHOTO: Download via user session, then send via BOT
                await _clear_status()
                try:
                    logger.info("Sending photo: downloading...")
                    photo_path = await target_msg.download_media()
                    if photo_path:
                        logger.info("Sending photo via BOT...")
                        await event.reply(
                            text or " ",
                            file=photo_path,
                            buttons=buttons,
                            link_preview=False,
                        )
                        try:
                            os.remove(photo_path)
                        except Exception:
                            pass
                        return
                except Exception as e:
                    logger.error(f"Photo download+send failed: {e}")
                    try:
                        await event.reply(
                            text or " ",
                            file=target_msg.media,
                            buttons=buttons,
                            link_preview=False,
                        )
                        return
                    except Exception as e2:
                        logger.error(f"Direct photo send also failed: {e2}")
                        try:
                            await user.send_file(
                                event.chat_id,
                                file=target_msg.media,
                                caption=text or None,
                            )
                            if buttons:
                                await event.reply("👆", buttons=buttons, link_preview=False)
                            return
                        except Exception as e3:
                            logger.error(f"User photo send also failed: {e3}")

            elif is_video:
                # VIDEO: Multiple delivery strategies
                logger.info("Video detected, trying delivery strategies...")

                # Strategy 0: Relay through a shared log chat — INSTANT, any size.
                # `user` has no access_hash for the end-user's chat (it has never
                # talked to them), so strategies 1/2 below fail regardless of
                # forward protection. Routing through a chat BOTH `user` and
                # `bot` are already members of sidesteps that entirely.
                if LOG_CHAT_ID:
                    try:
                        t0 = time.time()
                        log_msg = await user.forward_messages(LOG_CHAT_ID, target_msg)
                        await bot.forward_messages(event.chat_id, log_msg, from_peer=LOG_CHAT_ID)
                        logger.info(f"Log-chat relay succeeded in {time.time() - t0:.1f}s")
                        await _clear_status()
                        if buttons:
                            await event.reply("👆 Video sent above!", buttons=buttons, link_preview=False)
                        try:
                            await log_msg.delete()
                        except Exception:
                            pass
                        return
                    except Exception as e0:
                        logger.error(f"Log-chat relay failed: {e0}")

                # Strategy 1: Try user.send_file() directly
                try:
                    logger.info("Trying USER session direct send...")
                    await user.send_file(
                        event.chat_id,
                        file=target_msg.media,
                        caption=text or None,
                        supports_streaming=True,
                    )
                    if buttons:
                        await event.reply("👆 Video sent above!", buttons=buttons, link_preview=False)
                    await _clear_status()
                    return
                except Exception as e:
                    logger.error(f"User direct send failed: {e}")

                # Strategy 2: Forward message via user session
                try:
                    logger.info("Trying USER session forward...")
                    await user.forward_messages(
                        event.chat_id,
                        target_msg,
                    )
                    if buttons:
                        await event.reply("👆 Video forwarded above!", buttons=buttons, link_preview=False)
                    await _clear_status()
                    return
                except Exception as e:
                    logger.error(f"User forward failed: {e}")

                # Strategy 3: Download via user session, then upload via BOT
                # (only reached if LOG_CHAT_ID isn't set, or the relay itself
                # failed). This is a genuine two-hop transfer, so time WILL
                # scale with file size — set LOG_CHAT_ID above to avoid this
                # path entirely.
                try:
                    doc_size = doc.size if doc else 0
                    t0 = time.time()
                    logger.info(f"Trying download + BOT upload... size={doc_size/1_048_576:.1f}MB")
                    if status_msg:
                        try:
                            await status_msg.edit("📥 Downloading video... 0%")
                        except Exception:
                            pass

                    media_path = await target_msg.download_media(
                        progress_callback=_make_progress_cb(status_msg, "📥 Downloading video...")
                    )
                    if media_path:
                        t1 = time.time()
                        logger.info(f"Download done in {t1 - t0:.1f}s")
                        if status_msg:
                            try:
                                await status_msg.edit("📤 Uploading video... 0%")
                            except Exception:
                                pass

                        await event.reply(
                            text or " ",
                            file=media_path,
                            buttons=buttons,
                            link_preview=False,
                            supports_streaming=True,
                            progress_callback=_make_progress_cb(status_msg, "📤 Uploading video..."),
                        )
                        logger.info(
                            f"Upload done in {time.time() - t1:.1f}s "
                            f"(total {time.time() - t0:.1f}s, size={doc_size/1_048_576:.1f}MB)"
                        )
                        try:
                            os.remove(media_path)
                        except Exception:
                            pass
                        await _clear_status()
                        return
                except Exception as e2:
                    logger.error(f"Download & upload failed: {e2}")

                # All strategies failed
                await _clear_status()
                await event.reply(
                    "❌ Could not deliver video. Please try /start again.",
                    buttons=buttons,
                    link_preview=False,
                )

            else:
                # OTHER MEDIA: BOT with media reference
                await _clear_status()
                try:
                    await event.reply(
                        text or " ",
                        file=target_msg.media,
                        buttons=buttons,
                        link_preview=False,
                    )
                    return
                except Exception as e:
                    logger.error(f"Media send failed: {e}")
                    try:
                        await user.send_file(
                            event.chat_id,
                            file=target_msg.media,
                            caption=text or None,
                        )
                        if buttons:
                            await event.reply("👆", buttons=buttons, link_preview=False)
                        return
                    except Exception as e2:
                        logger.error(f"User send also failed: {e2}")

        # Text only (no media or media failed)
        await _clear_status()
        if text:
            await event.reply(text, buttons=buttons, link_preview=False)
        else:
            logger.warning("Empty response from target — no text, no media")
            await event.reply("✅ Done", buttons=buttons, link_preview=False)
    else:
        await _clear_status()
        await event.reply("❌ Target bot not responding. Try /start again.")


# ---------------------------------------------------------------------------
# Our Bot handlers — proxy everything to TARGET bot
# ---------------------------------------------------------------------------
@bot.on(events.NewMessage(pattern="/start"))
async def start_handler(event):
    """User sends /start → forward to TARGET bot → send response back."""
    text = event.raw_text.strip()

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
        timeout = 180.0
    else:
        status = await event.reply("⏳ Processing...")
        timeout = 30.0

    try:
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

    button_text = event.data.decode("utf-8")[4:]

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
        return

    status = await event.reply("⏳ Processing...")

    try:
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

    if user:
        try:
            await user.start()
            me = await user.get_me()
            logger.info(f"✅ User session started: {me.first_name} (@{me.username})")

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

    await bot.start(bot_token=BOT_TOKEN)
    me = await bot.get_me()
    logger.info(f"✅ Bot started: @{me.username}")
    logger.info(f"   Proxy target: {TARGET_BOT}")
    logger.info(f"   Channel: {CHANNEL_URL}")
    logger.info(f"   Group: {GROUP_URL}")

    if LOG_CHAT_ID:
        try:
            # Telethon can't message/forward-from a peer it has never seen,
            # even one you're an admin of, until it has listed dialogs (or
            # otherwise resolved that chat) at least once per client/session.
            await user.get_dialogs()
            await bot.get_dialogs()
            log_entity = await user.get_entity(LOG_CHAT_ID)
            await bot.get_entity(LOG_CHAT_ID)
            logger.info(f"✅ LOG_CHAT_ID resolved: {getattr(log_entity, 'title', LOG_CHAT_ID)}")
        except Exception as e:
            logger.error(f"❌ Could not resolve LOG_CHAT_ID '{LOG_CHAT_ID}': {e}")
            logger.error("   Make sure BOTH the user account and the bot are members/admins of that chat.")

    await bot.run_until_disconnected()


if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"Flask keep-alive running on port {PORT}")

    asyncio.run(main())
