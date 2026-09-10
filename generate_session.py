"""
SESSION STRING GENERATOR for KING MULTIVERSE Bot
=================================================
Uses raw Telethon to avoid Pyrogram's event loop issues on Python 3.14.

Usage:
    pip install telethon
    python generate_session.py

Enter your API_ID, API_HASH, phone number and OTP when prompted.
Copy the output string and set it as SESSION_STRING on Render.
"""

from telethon.sync import TelegramClient

API_ID = int(input("Enter API_ID: "))
API_HASH = input("Enter API_HASH: ")

client = TelegramClient("king_session", API_ID, API_HASH)

with client:
    session_string = client.session.save()
    print("\n" + "=" * 60)
    print("YOUR SESSION STRING (copy everything below):")
    print("=" * 60)
    print(session_string)
    print("=" * 60)
    print("\n✅ Copy this string and set it as SESSION_STRING on Render")
