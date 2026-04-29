# 🎬 YouTube Job Alert Generator — Setup Guide

> Fully automated system that scrapes Indian job portals, generates ~60-second
> narrated videos, and uploads them to YouTube — twice a day, hands-free.

---

## 📋 Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.10+ | Any modern version |
| FFmpeg | 4.x+ | Installed via apt on Ubuntu/CI |
| Git | any | For pushing to GitHub |
| Google Account | — | For YouTube channel |

---

## 🗂 Project Structure

```
youtube-job-alerts/
├── .github/
│   └── workflows/
│       └── daily_run.yml         ← GitHub Actions schedule
├── src/
│   ├── scraper.py                ← Job scraping (FreeJobAlert, Internshala, NCS)
│   ├── script_generator.py       ← Unique narration script templates
│   ├── tts.py                    ← gTTS text-to-speech
│   ├── video_generator.py        ← FFmpeg video assembly
│   ├── image_fetcher.py          ← Pixabay image download + caching
│   ├── thumbnail_generator.py    ← PIL thumbnail creation
│   ├── youtube_uploader.py       ← YouTube Data API v3 upload
│   └── utils.py                  ← Shared helpers
├── assets/
│   ├── fonts/                    ← Auto-downloaded Roboto fonts
│   └── backgrounds/              ← Optional custom background images
├── cache/
│   └── images/                   ← Cached Pixabay images (auto-managed)
├── data/
│   └── processed_jobs.json       ← Tracks already-processed jobs
├── output/                       ← Generated videos (temp, cleaned after upload)
├── main.py                       ← Orchestrator
├── config.py                     ← All configuration
├── requirements.txt
├── .env.example                  ← Copy to .env for local dev
└── setup.md                      ← This file
```

---

## ⚡ STEP-BY-STEP SETUP

### STEP 1 — Fork & Clone the Repository

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/youtube-job-alerts.git
cd youtube-job-alerts

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Install FFmpeg (Ubuntu/Debian)
sudo apt install ffmpeg
# macOS: brew install ffmpeg
# Windows: https://ffmpeg.org/download.html
```

---

### STEP 2 — Get a FREE Pixabay API Key

1. Go to **https://pixabay.com/api/docs/**
2. Create a free account
3. Copy your **API Key** from the dashboard
4. It looks like: `12345678-abcdef1234567890abcdef12`

> ⚠️ Without this key, the system uses auto-generated gradient backgrounds (still works!).

---

### STEP 3 — Google Cloud Setup (YouTube API)

#### 3a. Create a Google Cloud Project

1. Go to **https://console.cloud.google.com/**
2. Click **"New Project"** → name it `youtube-job-alerts`
3. Select the project

#### 3b. Enable YouTube Data API

1. Go to **APIs & Services → Library**
2. Search **"YouTube Data API v3"**
3. Click **Enable**

#### 3c. Create OAuth2 Credentials

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth Client ID**
3. If prompted, configure **OAuth consent screen**:
   - Type: **External**
   - App name: `Job Alert Bot`
   - Add your email
   - Scopes: add `youtube.upload`
   - Add your email as a **Test User**
4. Application type: **Desktop app**
5. Name: `job-alert-desktop`
6. Click **Create**
7. **Download JSON** → rename it to `client_secrets.json`
8. Place `client_secrets.json` in the project root

> 🔒 NEVER commit `client_secrets.json` or `token.json` to git!
> Add them to `.gitignore`.

---

### STEP 4 — First-Time OAuth Token (Local)

Run this **once on your local machine** to authorize the app:

```bash
# Copy .env.example to .env
cp .env.example .env

# Edit .env and fill in:
# PIXABAY_API_KEY=your_key_here
# YOUTUBE_UPLOAD_ENABLED=true

# Run with upload DISABLED first (test pipeline)
YOUTUBE_UPLOAD_ENABLED=false python main.py
```

Then run with upload enabled to generate the `token.json`:

```bash
python main.py
# A browser window will open → Log in → Allow access
# token.json is created automatically
```

---

### STEP 5 — Configure GitHub Secrets

Go to your GitHub repo → **Settings → Secrets and variables → Actions → New secret**

Add these secrets:

| Secret Name | Value | How to get |
|-------------|-------|-----------|
| `PIXABAY_API_KEY` | Your Pixabay key | Step 2 above |
| `YOUTUBE_TOKEN_JSON` | Base64-encoded token.json | See below |

#### Encode token.json for GitHub:

```bash
# Linux/Mac
base64 -w 0 token.json

# Windows (PowerShell)
[Convert]::ToBase64String([IO.File]::ReadAllBytes("token.json"))
```

Copy the entire base64 output and paste it as the `YOUTUBE_TOKEN_JSON` secret value.

---

### STEP 6 — Push to GitHub

```bash
# Make sure these are in .gitignore
echo "token.json" >> .gitignore
echo "client_secrets.json" >> .gitignore
echo ".env" >> .gitignore
echo "output/" >> .gitignore

git add .
git commit -m "feat: initial YouTube job alert system"
git push origin main
```

---

### STEP 7 — Test the GitHub Action

1. Go to your GitHub repo → **Actions** tab
2. Click **"YouTube Job Alert Generator"**
3. Click **"Run workflow"**
4. Set `max_videos` to `1` and `upload_enabled` to `false` for a dry run
5. Watch the logs — it should complete in under 5 minutes

---

### STEP 8 — Enable Scheduled Runs

The workflow is already scheduled for:
- **9:00 AM IST** (3:30 AM UTC)
- **6:00 PM IST** (12:30 PM UTC)

GitHub Actions runs automatically on this schedule. No additional setup needed!

---

## 🔄 How the Pipeline Works

```
[GitHub Actions Cron]
        ↓
[Scrape Jobs] ← FreeJobAlert + Internshala + NCS
        ↓
[Deduplicate] ← Compare against data/processed_jobs.json
        ↓
[For each new job (max 4)]
        ↓
[Generate Script] ← Template-based 110-word narration
        ↓
[Text-to-Speech] ← gTTS Indian English → MP3
        ↓
[Fetch Background] ← Pixabay API → cached locally
        ↓
[Build Slides] ← Pillow PNG slides (intro/details/salary/CTA)
        ↓
[Generate Thumbnail] ← PIL bold-text thumbnail
        ↓
[FFmpeg Assembly] ← Slides + Audio + Subtitles → MP4
        ↓
[YouTube Upload] ← Title, Description, Tags, Thumbnail
        ↓
[Save to processed_jobs.json]
```

---

## ⏱ GitHub Actions Quota Usage

| Metric | Value |
|--------|-------|
| Runs per day | 2 |
| Minutes per run | ~6–8 min |
| Days per month | 30 |
| **Total/month** | **~360–480 min** |
| GitHub free quota | 2,000 min/month |
| **Headroom** | **~1,500 min remaining** ✅ |

---

## 📊 YouTube API Quota

YouTube Data API gives **10,000 units/day** free.

| Operation | Cost |
|-----------|------|
| Video upload | 1,600 units |
| Thumbnail upload | 50 units |
| **Per video** | **~1,650 units** |
| **4 videos/day** | **~6,600 units** |
| **Daily limit** | **10,000 units** ✅ |

---

## 🐛 Troubleshooting

### "No new jobs to process"
→ All scraped jobs are already in `processed_jobs.json`.
→ Delete or clear `data/processed_jobs.json` to reprocess.

### "gTTS failed"
→ Google TTS has rate limits. The system retries 3 times automatically.
→ If persists, wait a few minutes and re-run.

### "FFmpeg not found"
→ Install FFmpeg: `sudo apt install ffmpeg` (Ubuntu) or `brew install ffmpeg` (Mac).

### "YouTube token expired"
→ Re-run Step 4 locally to refresh `token.json`.
→ Re-encode and update the `YOUTUBE_TOKEN_JSON` GitHub secret.

### "Pixabay returns no results"
→ Check your API key is correct in `.env` / GitHub Secrets.
→ System auto-falls back to generated gradient backgrounds.

### Scrapers return empty results
→ Job sites may have changed their HTML structure.
→ System uses `_get_fallback_jobs()` automatically — pipeline continues.
→ Check `src/scraper.py` and update CSS selectors if needed.

---

## 🔧 Customization

### Change Upload Schedule
Edit `.github/workflows/daily_run.yml`:
```yaml
schedule:
  - cron: "30 3 * * *"    # 9:00 AM IST
  - cron: "30 12 * * *"   # 6:00 PM IST
```
Use https://crontab.guru to generate cron expressions.

### Change Max Videos Per Run
In `.env` or GitHub Actions env:
```
MAX_VIDEOS_PER_RUN=2
```

### Add Custom Background Images
Place `.jpg` files in `assets/backgrounds/` — the system will use them as fallback.

### Customize Video Templates / Colors
Edit `src/video_generator.py` → `BG_COLORS` dict and color constants.

### Customize Thumbnail Colors
Edit `src/thumbnail_generator.py` → `COLOR_SCHEMES` list.

---

## 🔒 Security Notes

- `token.json` and `client_secrets.json` contain sensitive credentials
- Always add them to `.gitignore`
- Rotate your OAuth credentials periodically
- The Pixabay API key is low-risk but still keep it secret

---

## 📞 Support

If scraping fails on a source, the system automatically:
1. Logs the error
2. Skips to the next source
3. Uses fallback job data if all sources fail

The pipeline **never crashes completely** — it always produces output.
