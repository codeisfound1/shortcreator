# README.md
# YouTube Shorts Automation

Automatically create YouTube Shorts from Telegram channel content.

## Setup

1. **Get Telegram API Token:**
   - Create bot via @BotFather
   - Get HTTP API token

2. **YouTube API Setup:**
   - Go to [Google API Console](https://console.cloud.google.com/apis/dashboard)
   - Create project
   - Enable YouTube Data API v3
   - Create OAuth 2.0 credentials
   - Download `client_secrets.json`

3. **Prepare Music:**
   - Provide music file path or URL to permissively licensed music
   - Music will be cached locally

4. **Set Environment Variables:**
   ```bash
   export TELEGRAM_TOKEN="your_telegram_api_token"
   export TELEGRAM_CHANNELS='["@channel1", "@channel2"]'
   export YOUTUBE_CLIENT_SECRETS='{"client_id": "...", "client_secret": "...", "refresh_token": "..."}'
   export TITLE_TEMPLATE="Your Title Template"
   export DESCRIPTION="Video description"
   export TAGS='["tag1", "tag2"]'
   export PRIVACY_STATUS="private"
   export DURATION=15
   export MUSIC_OPTION="https://example.com/music.mp3"
   export FONT_PATH="path/to/custom/font.ttf"
