"""
Run this ONCE to exchange your authorization code for access_token + refresh_token.
Usage: python get_tiktok_tokens.py
"""

import requests

# ── Fill these in ──────────────────────────────────────────────
CLIENT_KEY    = "sbawtfufg4q6a68j4z"
CLIENT_SECRET = "dWi0TDfOnv1pxl68PHQdqGgBxmgrPM2N"
CODE          = "13I_rM6sagGuy8xkFvFujtEkTq67JE8-aa0kFKsvUnispj4rijyRo6hhth9B4q3qMlWAFXzMFIqnmHqHfoebYGJ36VBNaaH4-jkbMO4MOmuvvOSMlOA0cXM3NG1j81BKr7mLgJ4bdLrOrm-RvXvOxsTCDKXPC3lI4ILpx6QBJ9PMhTbia-qw-IAN9AEr9cCQFTIKWJvIPWCLvB0-k4lR7_aDKjfloCXeg1oghA%2Av%216216.s1"   # the code=... from the browser URL
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
    output = {
        "TIKTOK_ACCESS_TOKEN": data["access_token"],
        "TIKTOK_REFRESH_TOKEN": data.get("refresh_token"),
        "expires_in": data.get("expires_in"),
        "expires_in_hours": data.get("expires_in", 0) // 3600,
        "open_id": data.get("open_id"),
    }
    # Optional: remove None values
    output = {k: v for k, v in output.items() if v is not None}

    filename = "tiktok_tokens.json"
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("\n❌ ERROR saving JSON:", e)
        sys.exit(1)

    print(f"\n✅ SUCCESS — saved tokens to {filename}\n")
    print(f"  TIKTOK_ACCESS_TOKEN  = {output['TIKTOK_ACCESS_TOKEN']}")
    if "TIKTOK_REFRESH_TOKEN" in output:
        print(f"  TIKTOK_REFRESH_TOKEN = {output['TIKTOK_REFRESH_TOKEN']}")
    if "expires_in" in output:
        print(f"  Expires in           = {output['expires_in']} seconds (~{output['expires_in_hours']}h)")
    if "open_id" in output:
        print(f"  Open ID              = {output['open_id']}")
else:
    print("\n❌ ERROR:")
    print(data)
    print("\nCommon fixes:")
    print("  - Code already used? Re-run the browser auth URL to get a fresh code.")
    print("  - redirect_uri must match EXACTLY what you set in the developer portal.")
