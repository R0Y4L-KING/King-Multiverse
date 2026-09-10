# 👑 KING MULTIVERSE Bot

Telegram Bot: **@KING_Multiverse_Robot**

## Features
- Welcome message with banner image on `/start`
- Inline buttons: Join Channel + Join Group
- Flask keep-alive server for Render free tier

## Environment Variables (set on Render)

| Variable    | Description                          |
|-------------|--------------------------------------|
| `BOT_TOKEN` | Telegram bot token from @BotFather  |
| `API_ID`    | Telegram API ID from my.telegram.org |
| `API_HASH`  | Telegram API hash from my.telegram.org |

## Deploy on Render

1. Go to [render.com](https://render.com) → New → Web Service
2. Connect your GitHub repo `King-Multiverse`
3. **Build Command:** `pip install -r requirements.txt`
4. **Start Command:** `python bot.py`
5. Add environment variables (BOT_TOKEN, API_ID, API_HASH)
6. Deploy!

## Run Locally

```bash
pip install -r requirements.txt
export BOT_TOKEN="your_bot_token"
export API_ID="your_api_id"
export API_HASH="your_api_hash"
python bot.py
```

## Links
- Channel: https://t.me/ModAppsKing
- Group: https://t.me/ANONYMOUS_GROUP_KING
