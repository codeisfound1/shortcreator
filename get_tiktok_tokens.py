"""
Run this ONCE to exchange your authorization code for access_token + refresh_token.
Usage: python get_tiktok_tokens.py
"""

import requests

# ── Fill these in ──────────────────────────────────────────────
CLIENT_KEY    = "sbawtfufg4q6a68j4z"
CLIENT_SECRET = "dWi0TDfOnv1pxl68PHQdqGgBxmgrPM2N"
CODE          = "9wyCbkfyVKV4bfcX5JWIyA9MTlPyoBNDEug5q1toQMgWNCzW8_1l-6ApKs412uTkTtOGOSKK7yUB-IgXI-R48gslQf9GVhg5uEL52s0lOtLArPzKh-wZE5-PI56WU7DUPxYoowdCVCDHhucbVtalk87IjP5sPV0iSQF9sp3Fvn9alFr-kB7p1S-n_TX6cHEe-uQmXJ1RH9lMENv7E1vNTOHsJnzLCYd1e3rhlQ%2Av%216242.s1"   # the code=... from the browser URL
REDIRECT_URI  = "https://oauth.pstmn.io/v1/callback"
# ───────────────────────────────────────────────────────────────

resp = requests.post(
    "https://open.tiktokapis.com/v2/oauth/token/",
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    data={
        "client_key":    CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "code":          CODE,
        "grant_type":    "authorization_code",
        "redirect_uri":  REDIRECT_URI,
    },
)

data = resp.json()

if "access_token" in data:
    print("\n✅ SUCCESS — save these values as GitHub Secrets:\n")
    print(f"  TIKTOK_ACCESS_TOKEN  = {data['access_token']}")
    print(f"  TIKTOK_REFRESH_TOKEN = {data['refresh_token']}")
    print(f"  Expires in           = {data.get('expires_in')} seconds (~{data.get('expires_in', 0)//3600}h)")
    print(f"  Open ID              = {data.get('open_id')}")
else:
    print("\n❌ ERROR:")
    print(data)
    print("\nCommon fixes:")
    print("  - Code already used? Re-run the browser auth URL to get a fresh code.")
    print("  - redirect_uri must match EXACTLY what you set in the developer portal.")
