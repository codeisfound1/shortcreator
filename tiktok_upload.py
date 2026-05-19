"""
tiktok_upload.py
────────────────
Automatically upload a video to TikTok with:
  - Auto token refresh (tokens expire every 24h)
  - Chunked upload for large files
  - Upload status polling until TikTok finishes processing
  - Saves tokens back to file so next run reuses them

Usage:
    python tiktok_upload.py --video output_short.mp4 --title "Your caption #fyp"

Or set env vars and call upload_to_tiktok() from short_creator.py
"""

import argparse
import json
import math
import os
import time
from pathlib import Path

import requests

# ── Config ────────────────────────────────────────────────────────────────────
CLIENT_KEY    = os.getenv("TIKTOK_CLIENT_KEY",    "YOUR_CLIENT_KEY")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
TOKENS_FILE   = "tiktok_tokens.json"   # auto-saved after each refresh

CHUNK_SIZE    = 10 * 1024 * 1024       # 10 MB chunks (TikTok min: 5 MB, max: 64 MB)
MAX_POLL      = 30                     # max status checks before giving up
POLL_INTERVAL = 5                      # seconds between status checks

PRIVACY       = "SELF_ONLY"            # sandbox safe; change to PUBLIC_TO_EVERYONE after review
# ─────────────────────────────────────────────────────────────────────────────


# ── Token management ──────────────────────────────────────────────────────────

def load_tokens() -> dict:
    """Load tokens from file or environment variables."""
    # Prefer file (updated by refresh) over env vars
    if Path(TOKENS_FILE).exists():
        with open(TOKENS_FILE) as f:
            return json.load(f)
    return {
        "access_token":  os.getenv("TIKTOK_ACCESS_TOKEN", ""),
        "refresh_token": os.getenv("TIKTOK_REFRESH_TOKEN", ""),
        "open_id":       os.getenv("TIKTOK_OPEN_ID", ""),
    }


def save_tokens(tokens: dict):
    """Persist tokens so next run doesn't need re-auth."""
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)
    print(f"💾 Tokens saved to {TOKENS_FILE}")


def refresh_access_token(refresh_token: str) -> dict:
    """Exchange refresh_token for a new access_token."""
    print("🔄 Refreshing access token...")
    resp = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key":    CLIENT_KEY,
            "client_secret": CLIENT_SECRET,
            "grant_type":    "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(f"Token refresh failed: {data}")
    print("✅ Token refreshed successfully")
    return data


def get_valid_token() -> tuple[str, str]:
    """Return (access_token, open_id), refreshing if needed."""
    tokens = load_tokens()
    access_token  = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")
    open_id       = tokens.get("open_id", "")

    if not access_token:
        raise RuntimeError("No access_token found. Run get_tiktok_tokens.py first.")

    # Check if token is still valid
    resp = requests.get(
        "https://open.tiktokapis.com/v2/user/info/",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"fields": "open_id"},
    )
    if resp.status_code == 401:
        # Token expired — refresh it
        new_tokens = refresh_access_token(refresh_token)
        tokens.update(new_tokens)
        save_tokens(tokens)
        access_token = tokens["access_token"]
        open_id      = tokens.get("open_id", open_id)

    return access_token, open_id


# ── Upload ────────────────────────────────────────────────────────────────────

def init_upload(access_token: str, video_path: str, title: str) -> tuple[str, str]:
    """
    Tell TikTok we're about to upload. Returns (publish_id, upload_url).
    Uses chunked upload if file > CHUNK_SIZE, direct POST otherwise.
    """
    file_size   = Path(video_path).stat().st_size
    chunk_count = math.ceil(file_size / CHUNK_SIZE)

    print(f"📋 Initialising upload: {file_size/1024/1024:.1f} MB, {chunk_count} chunk(s)")

    resp = requests.post(
        "https://open.tiktokapis.com/v2/post/publish/video/init/",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type":  "application/json; charset=UTF-8",
        },
        json={
            "post_info": {
                "title":           title[:150],   # TikTok max title length
                "privacy_level":   PRIVACY,
                "disable_duet":    False,
                "disable_comment": False,
                "disable_stitch":  False,
            },
            "source_info": {
                "source":            "FILE_UPLOAD",
                "video_size":        file_size,
                "chunk_size":        min(CHUNK_SIZE, file_size),
                "total_chunk_count": chunk_count,
            },
        },
    )
    data = resp.json()
    if resp.status_code != 200 or "data" not in data:
        raise RuntimeError(f"Init upload failed: {data}")

    publish_id = data["data"]["publish_id"]
    upload_url = data["data"]["upload_url"]
    print(f"✅ Upload initialised. Publish ID: {publish_id}")
    return publish_id, upload_url


def upload_chunks(upload_url: str, video_path: str):
    """Upload the video file in chunks to TikTok's upload URL."""
    file_size = Path(video_path).stat().st_size
    chunk_num = 0

    with open(video_path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break

            start = chunk_num * CHUNK_SIZE
            end   = start + len(chunk) - 1

            print(f"  ⬆️  Uploading chunk {chunk_num + 1}: bytes {start}-{end}/{file_size}")

            resp = requests.put(
                upload_url,
                headers={
                    "Content-Type":  "video/mp4",
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Content-Length": str(len(chunk)),
                },
                data=chunk,
            )

            if resp.status_code not in (200, 206):
                raise RuntimeError(f"Chunk {chunk_num} upload failed: {resp.status_code} {resp.text}")

            chunk_num += 1

    print(f"✅ All {chunk_num} chunk(s) uploaded")


def poll_status(access_token: str, publish_id: str) -> str:
    """
    Poll until TikTok finishes processing.
    Returns final status string.
    """
    print(f"⏳ Polling status for publish_id={publish_id} ...")

    for attempt in range(1, MAX_POLL + 1):
        resp = requests.post(
            "https://open.tiktokapis.com/v2/post/publish/status/fetch/",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type":  "application/json; charset=UTF-8",
            },
            json={"publish_id": publish_id},
        )
        data = resp.json()
        status = data.get("data", {}).get("status", "UNKNOWN")
        print(f"  [{attempt}/{MAX_POLL}] Status: {status}")

        if status in ("PUBLISH_COMPLETE", "SUCCESS"):
            print("🎉 Video successfully published to TikTok!")
            return status
        if status in ("FAILED", "ERROR"):
            reason = data.get("data", {}).get("fail_reason", "unknown")
            raise RuntimeError(f"TikTok processing failed: {reason}")

        time.sleep(POLL_INTERVAL)

    raise RuntimeError(f"Upload timed out after {MAX_POLL * POLL_INTERVAL}s. Check TikTok Studio manually.")


# ── Main entry point ──────────────────────────────────────────────────────────

def upload_to_tiktok(video_path: str, title: str) -> str:
    """
    Full upload flow. Returns publish_id on success.
    Call this from short_creator.py after YouTube upload.
    """
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    print(f"\n🎵 Starting TikTok upload: {video_path}")

    access_token, open_id = get_valid_token()
    publish_id, upload_url = init_upload(access_token, video_path, title)
    upload_chunks(upload_url, video_path)
    final_status = poll_status(access_token, publish_id)

    print(f"\n✅ Done! publish_id={publish_id}, status={final_status}")
    return publish_id


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload a video to TikTok")
    parser.add_argument("--video", required=True, help="Path to the .mp4 file")
    parser.add_argument("--title", default="Auto-generated Short #fyp #shorts", help="Video caption/title")
    args = parser.parse_args()

    upload_to_tiktok(args.video, args.title)
