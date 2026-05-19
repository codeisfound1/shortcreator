"""
Run this ONCE to exchange your authorization code for access_token + refresh_token.
Usage: python get_tiktok_tokens.py
"""

import requests

# ── Fill these in ──────────────────────────────────────────────
CLIENT_KEY    = "sbawtfufg4q6a68j4z"
CLIENT_SECRET = "dWi0TDfOnv1pxl68PHQdqGgBxmgrPM2N"
CODE          = "bHZu2dhrmDKd_sTPa7fQSNhtBQ_voqXvX2UtkzyxbrO8VlKVPI_9A0Cl2Rgz2nvhnCoplfS0jubt9OdXkCzGHlMod5Mw7gq5stwZe0f13tcJB9rLWzNUNF8AGD5xRXZlL3-mwBeOU6ux_4r_tu4WeQlj2zWUwXEEksnj9bgn6fskHiMd6EiCawwwCnYXTrfY_zQ01odNy0w2n2DEciX-cz240_DPzpnx2xWAUQ%2Av%216167.s1"   # the code=... from the browser URL
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
