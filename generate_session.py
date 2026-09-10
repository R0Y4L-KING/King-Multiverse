"""
SESSION STRING GENERATOR for KING MULTIVERSE Bot
=================================================
Run this script locally to generate a valid Pyrogram v2 session string.

Usage:
    pip install pyrogram==2.0.106 tgcrypto==1.2.5
    python generate_session.py

Enter your API_ID, API_HASH, phone number and OTP when prompted.
Copy the output string and set it as SESSION_STRING on Render.
"""

from pyrogram import Client

API_ID = int(input("Enter API_ID: "))
API_HASH = input("Enter API_HASH: ")

app = Client(
    "king_session",
    api_id=API_ID,
    api_hash=API_HASH,
    in_memory=True,
)

with app:
    session_string = app.export_session_string()
    print("\n" + "=" * 60)
    print("YOUR SESSION STRING (copy everything below):")
    print("=" * 60)
    print(session_string)
    print("=" * 60)
    print("\n✅ Copy this string and set it as SESSION_STRING on Render")
