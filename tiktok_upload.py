"""
tiktok_upload.py
────────────────
Automatically upload a video to TikTok with:
  - Secrets loaded strictly from environment variables (GitHub Secrets / CI)
  - Auto token refresh (tokens expire every 24h)
  - Chunked upload for large files
  - Upload status polling until TikTok finishes processing
  - Saves refreshed tokens back to env-safe file for reuse within the same run

Usage (local):
    export TIKTOK_CLIENT_KEY=...
    export TIKTOK_CLIENT_SECRET=...
    export TIKTOK_ACCESS_TOKEN=...
    export TIKTOK_REFRESH_TOKEN=...
    export TIKTOK_OPEN_ID=...
    python tiktok_upload.py --video output_short.mp4 --title "Your caption #fyp"

GitHub Actions (add these as repository secrets):
    TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET,
    TIKTOK_ACCESS_TOKEN, TIKTOK_REFRESH_TOKEN, TIKTOK_OPEN_ID
"""

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import requests

# ── Config ────────────────────────────────────────────────────────────────────
CHUNK_SIZE    = 10 * 1024 * 1024       # 10 MB chunks (TikTok min: 5 MB, max: 64 MB)
MAX_POLL      = 30                     # max status checks before giving up
POLL_INTERVAL = 5                      # seconds between status checks
PRIVACY       = "SELF_ONLY"            # sandbox safe; change to PUBLIC_TO_EVERYONE after review

# Runtime token cache (in-memory, within one process lifetime)
_token_cache: dict = {}
# ─────────────────────────────────────────────────────────────────────────────


# ── Secret loading ────────────────────────────────────────────────────────────

def _require_env(name: str) -> str:
    """
    Return the value of an environment variable.
    Raises a clear error if it is missing or empty — no silent placeholder defaults.
    """
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required secret: {name}\n"
            f"  • Locally:  export {name}=<value>\n"
            f"  • GitHub:   Settings → Secrets → Actions → New repository secret"
        )
    return value


def load_secrets() -> dict:
    """
    Load all TikTok credentials from environment variables.
    Must be set as GitHub Secrets (or local env vars for development).
    """
    return {
        "client_key":     _require_env("TIKTOK_CLIENT_KEY"),
        "client_secret":  _require_env("TIKTOK_CLIENT_SECRET"),
        "access_token":   _require_env("TIKTOK_ACCESS_TOKEN"),
        "refresh_token":  _require_env("TIKTOK_REFRESH_TOKEN"),
        "open_id":        _require_env("TIKTOK_OPEN_ID"),
    }


# ── Token management ──────────────────────────────────────────────────────────

def refresh_access_token(client_key: str, client_secret: str, refresh_token: str) -> dict:
    """Exchange refresh_token for a new access_token."""
    print("🔄 Refreshing access token...")
    resp = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key":    client_key,
            "client_secret": client_secret,
            "grant_type":    "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(f"Token refresh failed: {data}")
    print("✅ Token refreshed successfully")
    return data


def get_valid_token() -> tuple[str, str]:
    """
    Return (access_token, open_id).
    Validates the current token against the TikTok API and refreshes if expired.
    Caches the result in memory for the duration of this process.
    """
    global _token_cache

    if not _token_cache:
        _token_cache = load_secrets()

    access_token  = _token_cache["access_token"]
    refresh_token = _token_cache["refresh_token"]
    open_id       = _token_cache["open_id"]
    client_key    = _token_cache["client_key"]
    client_secret = _token_cache["client_secret"]

    # Validate token with a lightweight API call
    resp = requests.get(
        "https://open.tiktokapis.com/v2/user/info/",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"fields": "open_id"},
        timeout=15,
    )

    if resp.status_code == 401:
        # Token expired — refresh and update cache
        new_tokens = refresh_access_token(client_key, client_secret, refresh_token)
        _token_cache.update(new_tokens)
        access_token = _token_cache["access_token"]
        open_id      = _token_cache.get("open_id", open_id)
        print(
            "⚠️  Access token was refreshed. Update TIKTOK_ACCESS_TOKEN (and "
            "TIKTOK_REFRESH_TOKEN if it changed) in your GitHub Secrets for the next run."
        )

    return access_token, open_id


# ── Upload ────────────────────────────────────────────────────────────────────

def init_upload(access_token: str, video_path: str, title: str) -> tuple[str, str]:
    """
    Tell TikTok we're about to upload.
    Returns (publish_id, upload_url).
    """
    file_size   = Path(video_path).stat().st_size
    chunk_count = math.ceil(file_size / CHUNK_SIZE)

    print(f"📋 Initialising upload: {file_size / 1024 / 1024:.1f} MB, {chunk_count} chunk(s)")

    resp = requests.post(
        "https://open.tiktokapis.com/v2/post/publish/video/init/",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type":  "application/json; charset=UTF-8",
        },
        json={
            "post_info": {
                "title":           title[:150],
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
        timeout=30,
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
                    "Content-Type":   "video/mp4",
                    "Content-Range":  f"bytes {start}-{end}/{file_size}",
                    "Content-Length": str(len(chunk)),
                },
                data=chunk,
                timeout=120,
            )

            if resp.status_code not in (200, 206):
                raise RuntimeError(
                    f"Chunk {chunk_num + 1} upload failed: {resp.status_code} {resp.text}"
                )
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
            timeout=15,
        )
        data   = resp.json()
        status = data.get("data", {}).get("status", "UNKNOWN")
        print(f"  [{attempt}/{MAX_POLL}] Status: {status}")

        if status in ("PUBLISH_COMPLETE", "SUCCESS"):
            print("🎉 Video successfully published to TikTok!")
            return status
        if status in ("FAILED", "ERROR"):
            reason = data.get("data", {}).get("fail_reason", "unknown")
            raise RuntimeError(f"TikTok processing failed: {reason}")

        time.sleep(POLL_INTERVAL)

    raise RuntimeError(
        f"Upload timed out after {MAX_POLL * POLL_INTERVAL}s. Check TikTok Studio manually."
    )


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
    parser.add_argument(
        "--title",
        default="Auto-generated Short #fyp #shorts",
        help="Video caption/title",
    )
    args = parser.parse_args()

    try:
        upload_to_tiktok(args.video, args.title)
    except RuntimeError as exc:
        print(f"\n❌ Error: {exc}", file=sys.stderr)
        sys.exit(1)
