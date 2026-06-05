"""Quick test for Angel One SmartAPI connection."""
import os
import sys
from pathlib import Path

import pyotp
from SmartApi import SmartConnect

# Load from environment
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.core.config import get_settings
settings = get_settings()

API_KEY = settings.angel_api_key
CLIENT_ID = settings.angel_client_id
PASSWORD = settings.angel_password
TOTP_SECRET = settings.angel_totp_secret

if not all([API_KEY, CLIENT_ID, PASSWORD, TOTP_SECRET]):
    print("ERROR: Angel One credentials not set in .env")
    print("Required: ANGEL_API_KEY, ANGEL_CLIENT_ID, ANGEL_PASSWORD, ANGEL_TOTP_SECRET")
    sys.exit(1)

print("Generating TOTP...")
totp = pyotp.TOTP(TOTP_SECRET).now()
print("TOTP:", totp)

print("Connecting to Angel One...")
obj = SmartConnect(api_key=API_KEY)
data = obj.generateSession(CLIENT_ID, PASSWORD, totp)

print("Status:", data.get("status"))
print("Message:", data.get("message"))

if data.get("status"):
    print("\nCONNECTION SUCCESSFUL!")

    profile = obj.getProfile(obj.refresh_token)
    pdata = profile.get("data", {})
    print("Name:", pdata.get("name", "N/A"))
    print("Client ID:", pdata.get("clientcode", "N/A"))
    print("Email:", pdata.get("email", "N/A"))

    # Test: get RELIANCE LTP
    try:
        ltp = obj.ltpData("NSE", "RELIANCE-EQ", "2885")
        print("\nRELIANCE quote:", ltp)
    except Exception as e:
        print("Quote test error:", e)

    obj.terminateSession(CLIENT_ID)
    print("\nSession closed. Angel One is ready!")
else:
    print("\nCONNECTION FAILED")
    print("Full response:", data)
    print("\nTroubleshooting:")
    print("  - Check if Client ID is correct (format: A123456)")
    print("  - Check if PIN is your trading MPIN")
    print("  - Check if TOTP secret is correct")
    print("  - Check if your IP is whitelisted on smartapi.angelone.in")
