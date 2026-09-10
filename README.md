# 👑 KING MULTIVERSE Bot

Telegram Bot: **@KING_Multiverse_Robot**

## Features
- Welcome message with banner image on `/start`
- Inline buttons: Join Channel, Join Group, Close
- **Session String support** — forward messages from main account/channel
- Flask keep-alive server for Render free tier
- `/status` command to check bot + user session status

## Environment Variables (set on Render)

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Telegram bot token from @BotFather |
| `API_ID` | Telegram API ID from my.telegram.org |
| `API_HASH` | Telegram API hash from my.telegram.org |
| `SESSION_STRING` | Pyrogram session string (for message forwarding) |

## How to get SESSION_STRING

1. Get API_ID and API_HASH from https://my.telegram.org → API Development Tools
2. Run this script locally:
```python
pip install pyrogram tgcrypto
python -c "
from pyrogram import Client
client = Client('session', api_id=YOUR_API_ID, api_hash='YOUR_API_HASH')
client.run()
# Enter phone number and verification code when prompted
# After login, run:
client = Client('session', api_id=YOUR_API_ID, api_hash='YOUR_API_HASH')
with client:
    print(client.export_session_string())
"
```
3. Copy the output string and set it as `SESSION_STRING` on Render

## Deploy on Render

1. Go to [render.com](https://render.com) → New → Web Service
2. Connect your GitHub repo `King-Multiverse`
3. **Build Command:** `pip install -r requirements.txt`
4. **Start Command:** `python bot.py`
5. Add environment variables (BOT_TOKEN, API_ID, API_HASH, SESSION_STRING)
6. Deploy!

## Run Locally

```bash
pip install -r requirements.txt
export BOT_TOKEN="your_bot_token"
export API_ID="your_api_id"
export API_HASH="your_api_hash"
export SESSION_STRING="your_session_string"
python bot.py
```

## Links
- Channel: https://t.me/ModAppsKing
- Group: https://t.me/ANONYMOUS_GROUP_KING
