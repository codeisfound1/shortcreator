# YouTube Shorts Automation

Automatically create YouTube Shorts from Telegram channel content.

---

## 🔑 Getting a New OAuth Refresh Token (Required for Playlist Support)

Playlist management requires the **full YouTube scope**. If you previously generated a token with only `youtube.upload`, you must get a new one. Follow these exact steps:

### Step-by-step via OAuth Playground

1. Go to **https://developers.google.com/oauthplayground/**

2. Click the **gear icon ⚙️** (top-right) → check **"Use your own OAuth credentials"**
   - Enter your **OAuth Client ID** and **OAuth Client Secret** from Google Cloud Console

3. In the left panel, find **"YouTube Data API v3"** and select this scope:
   ```
   https://www.googleapis.com/auth/youtube
   ```
   > ⚠️ Do NOT use `youtube.upload` — that scope alone blocks playlist operations.

4. Click **"Authorize APIs"** → sign in with your YouTube account → allow access

5. Click **"Exchange authorization code for tokens"**

6. Copy the **Refresh token** value shown

7. Build your `YOUTUBE_CLIENT_SECRETS` JSON secret (store in GitHub Secrets):
   ```json
   {
     "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
     "client_secret": "YOUR_CLIENT_SECRET",
     "refresh_token": "PASTE_NEW_REFRESH_TOKEN_HERE",
     "token_uri": "https://oauth2.googleapis.com/token"
   }
   ```

---

## Setup

### 1. Telegram Bot Token
- Create a bot via [@BotFather](https://t.me/BotFather)
- Add the bot as an **admin** to your channel(s)
- Copy the HTTP API token

### 2. YouTube API (Google Cloud Console)
- Go to [Google API Console](https://console.cloud.google.com/apis/dashboard)
- Create a project → enable **YouTube Data API v3**
- Create **OAuth 2.0 credentials** (type: Web application)
- Add `https://developers.google.com/oauthplayground` as an authorized redirect URI
- Download or note your Client ID + Secret

### 3. GitHub Secrets

| Secret | Value |
|--------|-------|
| `TELEGRAM_TOKEN` | Your Telegram bot token |
| `TELEGRAM_CHANNELS` | `["@yourchannel"]` (JSON array) |
| `YOUTUBE_CLIENT_SECRETS` | Full JSON with client_id, client_secret, refresh_token, token_uri |
| `PLAYLIST_ID` | `PL3B7UtjF3P8ya2XNvBX8fgKOoqsCza8dv` |

### 4. Optional env vars (with defaults)

| Variable | Default | Description |
|----------|---------|-------------|
| `PUBLISH_DELAY_HOURS` | `1` | Hours until scheduled publish |
| `BRAND_HASHTAGS` | `["cryptohieuqua","cryptohieu.com"]` | Always-on hashtags |
| `DURATION` | `15` | Minimum video duration (seconds) |
| `PRIVACY_STATUS` | `private` | Upload privacy (always private when scheduled) |
| `TAGS` | `["Shorts","Auto-generated"]` | Base YouTube tags |
| `DESCRIPTION` | `"Automated YouTube Short"` | Video description prefix |
| `MUSIC_OPTION` | *(built-in URL)* | Background music URL or file path |

---

## Features

- **Telegram → YouTube pipeline** — fetches latest image+caption from your channels
- **Duplicate prevention** — tracks processed message IDs in `.published_ids.json`; never uploads the same post twice
- **Vietnamese TTS** — reads caption aloud with `vi-VN-HoaiMyNeural` voice, appending *"Đừng quên đăng ký kênh..."*
- **Scheduled publish** — uploads as private, auto-publishes after 1 hour
- **Playlist auto-add** — every new video is added to your playlist immediately after upload
- **Brand hashtags** — `#cryptohieuqua #cryptohieu.com` on every video
- **Word-synced captions** — highlighted karaoke-style words over a Ken Burns zoom
- **Background music** — mixed at lower volume when TTS is present

---

## Run locally

```bash
pip install -r requirements.txt

export TELEGRAM_TOKEN="..."
export TELEGRAM_CHANNELS='["@yourchannel"]'
export YOUTUBE_CLIENT_SECRETS='{"client_id":"...","client_secret":"...","refresh_token":"...","token_uri":"https://oauth2.googleapis.com/token"}'
export PLAYLIST_ID="PL3B7UtjF3P8ya2XNvBX8fgKOoqsCza8dv"

python short_creator.py
```
# ShortCreator — Duplicate Prevention Guide

## How duplicates are prevented

Two layers work together to ensure the same Telegram post is never turned into a video twice.

### Layer 1 — Telegram `getUpdates` offset (primary)

Every time the bot calls Telegram's `getUpdates` API it passes an `offset` value. Telegram uses this as an acknowledgement cursor: once you pass `offset=N`, Telegram permanently marks all updates below N as seen and **never returns them again** — even if the bot restarts or the workflow re-runs.

The current offset is saved to `.telegram_offset.json` after every run.

### Layer 2 — Published IDs file (fallback)

Every `channel:message_id` that was successfully uploaded to YouTube is written to `.published_ids.json`. If `.telegram_offset.json` is ever lost or reset, this file acts as a second check and skips any post whose ID is already in the list.

---

## State files

| File | Purpose |
|---|---|
| `.telegram_offset.json` | Stores the `getUpdates` cursor per channel so Telegram never re-delivers old updates |
| `.published_ids.json` | Stores every `channel:message_id` that was already uploaded (fallback guard) |

Both files live in the **repo root**, same level as `short_creator.py`. They are committed to the repo so they persist across GitHub Actions runs.

---

## Setup — commit the state files to your repo

Because GitHub Actions runners are ephemeral (wiped after every run), the state files must be **committed to the repository** so `actions/checkout` restores them on every run.

### First-time setup

```bash
# In your local repo clone
touch .published_ids.json .telegram_offset.json
echo "[]" > .published_ids.json
echo "{}" > .telegram_offset.json

git add .published_ids.json .telegram_offset.json
git commit -m "chore: add initial state files for duplicate prevention"
git push
```

### How updates get saved back

The workflow uses the **write-back pattern**: after `short_creator.py` runs it updates both files on disk. The final workflow step commits and pushes any changes back to the repo automatically, so the next run starts with the latest state.

Make sure your workflow has **write permissions**. Go to:
`Settings → Actions → General → Workflow permissions → Read and write permissions`

---

## Workflow file — `.github/workflows/shortcreator.yml`

```yaml
on:
  schedule:
    - cron: '0 */8 * * *'  # Every 8 hours
  workflow_dispatch:  # Manual trigger

jobs:
  build-and-upload:
    runs-on: ubuntu-latest

    permissions:
      contents: write  # needed to push state files back

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Install fonts
        run: |
          sudo apt-get install -y fonts-dejavu-core fonts-noto-color-emoji
          pip install pilmoji

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.8'

      - name: Install sys dependencies
        run: sudo apt-get install -y ffmpeg

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run automation
        env:
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          TELEGRAM_CHANNELS: ${{ secrets.TELEGRAM_CHANNELS }}
          YOUTUBE_CLIENT_SECRETS: ${{ secrets.YOUTUBE_CLIENT_SECRETS }}
        run: python short_creator.py

      - name: Save state files back to repo
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add .published_ids.json .telegram_offset.json
          git diff --cached --quiet || git commit -m "chore: update state files [skip ci]"
          git push
```

> The `[skip ci]` tag in the commit message prevents the push from triggering another workflow run.

---

## File structure

```
shortcreator/
├── .github/
│   └── workflows/
│       └── shortcreator.yml
├── .published_ids.json     ← committed, updated each run
├── .telegram_offset.json   ← committed, updated each run
├── README.md
├── brand_logo.png
├── requirements.txt
└── short_creator.py
```

---

## Resetting the state

If you want to reprocess old posts (e.g. after a test), reset both files:

```bash
echo "[]" > .published_ids.json
echo "{}" > .telegram_offset.json
git add .published_ids.json .telegram_offset.json
git commit -m "chore: reset duplicate prevention state"
git push
```
