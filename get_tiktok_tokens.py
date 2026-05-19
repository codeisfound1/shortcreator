"""
get_tiktok_tokens.py
─────────────────────
1. Reads CLIENT_KEY, CLIENT_SECRET, CODE from GitHub Secrets (env vars)
2. Exchanges code for access_token + refresh_token
3. Automatically saves ALL 5 secrets back to GitHub repo secrets

Requirements:
    pip install requests PyNaCl

GitHub Secrets needed BEFORE running:
    TIKTOK_CLIENT_KEY     → your TikTok app client key
    TIKTOK_CLIENT_SECRET  → your TikTok app client secret
    TIKTOK_CODE           → the code= value from the browser redirect URL
    GH_TOKEN          → must have repo secrets write permission (Actions default token works)
    GH_REPO     → auto-set by GitHub Actions (e.g. "yourname/yourrepo")
"""

import base64
import os
import sys

import requests
from nacl import encoding, public  # PyNaCl — for encrypting secrets before sending to GitHub


# ── Read inputs from environment ──────────────────────────────────────────────
CLIENT_KEY    = os.environ["TIKTOK_CLIENT_KEY"]
CLIENT_SECRET = os.environ["TIKTOK_CLIENT_SECRET"]
CODE          = os.environ["TIKTOK_CODE"]
REDIRECT_URI  = "https://localhost/callback"

GITHUB_TOKEN  = os.environ["GH_TOKEN"]         # provided automatically by Actions
GITHUB_REPO   = os.environ["GH_REPO"]    # e.g. "yourname/shortcreator"
# ─────────────────────────────────────────────────────────────────────────────


# ── Step 1: Exchange code for tokens ─────────────────────────────────────────
print("🔄 Exchanging authorization code for tokens...")

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

if "access_token" not in data:
    print(f"\n❌ Token exchange failed:\n{data}")
    print("\nCommon fixes:")
    print("  - Code already used? Get a fresh one from the browser auth URL.")
    print("  - REDIRECT_URI must match exactly what you set in TikTok Developer Portal.")
    sys.exit(1)

ACCESS_TOKEN  = data["access_token"]
REFRESH_TOKEN = data["refresh_token"]
OPEN_ID       = data.get("open_id", "")
EXPIRES_IN    = data.get("expires_in", 0)

print(f"✅ Tokens received!")
print(f"   Open ID    : {OPEN_ID}")
print(f"   Expires in : {EXPIRES_IN // 3600}h")


# ── Step 2: Get GitHub repo public key (needed to encrypt secrets) ────────────
print(f"\n🔑 Fetching GitHub repo public key for {GITHUB_REPO}...")

key_resp = requests.get(
    f"https://api.github.com/repos/{GITHUB_REPO}/actions/secrets/public-key",
    headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    },
)

if key_resp.status_code != 200:
    print(f"❌ Failed to fetch GitHub public key: {key_resp.json()}")
    sys.exit(1)

key_data   = key_resp.json()
PUBLIC_KEY = key_data["key"]
KEY_ID     = key_data["key_id"]
print(f"✅ Got GitHub public key (key_id: {KEY_ID})")


# ── Step 3: Encrypt + push secrets to GitHub ──────────────────────────────────

def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    """Encrypt a secret using the repo's public key (GitHub requires this)."""
    public_key_bytes = base64.b64decode(public_key_b64)
    sealed_box = public.SealedBox(public.PublicKey(public_key_bytes))
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def push_secret(name: str, value: str):
    """Create or update a GitHub Actions secret."""
    encrypted = encrypt_secret(PUBLIC_KEY, value)
    r = requests.put(
        f"https://api.github.com/repos/{GITHUB_REPO}/actions/secrets/{name}",
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept":        "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={
            "encrypted_value": encrypted,
            "key_id":          KEY_ID,
        },
    )
    if r.status_code in (201, 204):
        print(f"   ✅ {name} saved")
    else:
        print(f"   ❌ {name} failed: {r.status_code} {r.json()}")


print("\n📤 Pushing all secrets to GitHub...")

push_secret("TIKTOK_CLIENT_KEY",    CLIENT_KEY)
push_secret("TIKTOK_CLIENT_SECRET", CLIENT_SECRET)
push_secret("TIKTOK_ACCESS_TOKEN",  ACCESS_TOKEN)
push_secret("TIKTOK_REFRESH_TOKEN", REFRESH_TOKEN)
push_secret("TIKTOK_OPEN_ID",       OPEN_ID)

print("\n🎉 All 5 secrets saved to GitHub successfully!")
print("   You can now delete TIKTOK_CODE from GitHub Secrets — it's a one-time use value.")
