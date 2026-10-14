---
title: AI Shorts Generator
emoji: 🎬
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# 🎬 AI Shorts Generator

Create viral YouTube Shorts from your videos and stories — **100% free, no paid APIs needed!**

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.10%2B-purple)

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📹 **Video Upload** | Upload any video (MP4, MOV, AVI, MKV, WEBM) |
| 🔗 **Paste a Link** | Paste a YouTube / Shorts / Instagram / TikTok link — the video is downloaded (up to 1080p) and dropped straight into the cropper |
| 📝 **Story Text** | Add your story that gets formatted as overlay text |
| 🤖 **AI Rewrite** | Auto-generate viral hooks using local Ollama/Llama 3 |
| 🎨 **Multiple Templates** | Choose from 8+ viral templates (Movie, Crime, Celebrity, etc.) |
| 💬 **Auto Subtitles** | Generate captions from video audio (optional) |
| 🏷️ **Viral Hashtags** | Auto-generated niche-specific hashtags |
| 🖼️ **Watermark** | Add your logo or channel name |
| 🎬 **1080×1920 Export** | Perfect vertical format for YouTube Shorts |
| 📊 **Export History** | Track all your generated videos |
| 🆓 **100% Free** | No OpenAI, ElevenLabs, or paid services needed |

## 📋 Layout

```
┌─────────────────────────┐
│    Story Text (top)     │
│                         │
├─────────────────────────┤
│                         │
│      Video (center)     │
│                         │
├─────────────────────────┤
│    Watermark (bottom)   │
└─────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

1. **Python 3.10+** — [Download](https://www.python.org/downloads/)
2. **FFmpeg** — [Download](https://ffmpeg.org/download.html) (Windows: `winget install ffmpeg`)
3. **yt-dlp** (for paste-a-link downloads) — included in `requirements.txt`, or `pip install yt-dlp`
4. **Ollama** (optional) — [Download](https://ollama.com/) + `ollama pull llama3`

> ⚠️ **Note on links:** only download videos you own or have the rights to use.
> Downloading third-party content may violate the source platform's Terms of Service.

### One-Click Setup

```bash
# Run the setup script
setup.bat
```

### Manual Setup

```bash
# 1. Navigate to backend
cd backend

# 2. Create virtual environment
python -m venv venv

# 3. Activate it
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Start the server
python app.py
```

### Open the App

👉 **http://localhost:8000**

## 🎯 How It Works

1. **Upload** a video (any short clip works great) — or **paste a link** and hit *Fetch Video* to download it
2. **Write** your story or fact
3. **Click** "✨ AI Rewrite" to generate a viral hook
4. **Choose** a template style
5. **Click** "Generate Viral Short" 🚀

The backend will:
- Scale and center your video in 1080×1920 format
- Overlay your story text at the top
- Add your logo/watermark at the bottom
- Generate subtitles (optional)
- Output a ready-to-upload MP4 file

## 🤖 AI Features (Free + Local)

### With Ollama (Recommended)
```bash
ollama pull llama3
```
The AI will:
- Rewrite stories into viral hooks
- Add curiosity gaps
- Suggest emojis
- Recommend hashtags

### Without Ollama
The generator still works using template-based hooks — no AI needed!

## 🎨 Templates

| Template | Best For |
|----------|----------|
| 🎬 Viral Movie Facts | Movie facts, BTS stories |
| 🌟 Celebrity Secrets | Celebrity gossip, unknown facts |
| 🔍 True Crime | Mystery stories, investigations |
| 🏆 Sports Highlights | Sports moments, athlete stories |
| 📖 Story Time | General storytelling |
| 💀 Reddit Stories | Viral Reddit content |
| ✨ Minimal Clean | Simple, elegant content |
| 🔥 Trending Now | Modern viral style |

## 📁 Project Structure

```
shorts-generator/
├── backend/
│   ├── app.py                    # FastAPI server
│   ├── database.py               # SQLite database
│   ├── requirements.txt          # Python dependencies
│   ├── services/
│   │   ├── editor.py             # FFmpeg video editing
   │   ├── downloader.py         # yt-dlp URL -> uploads/ video downloader
│   │   ├── ai.py                 # Ollama AI integration
│   │   ├── subtitle.py           # Whisper subtitle generation
│   │   └── template.py           # Template definitions
│   ├── assets/                   # Background, logo images
│   ├── uploads/                  # Uploaded videos
│   └── output/                   # Generated Shorts
├── frontend/
│   ├── index.html                # Web UI
│   ├── style.css                 # Styling
│   └── app.js                    # Frontend logic
├── setup.bat                     # Windows setup
└── README.md
```

## 🚀 Going Viral - Recommended Niches

| Niche | Viral Potential | RPM |
|-------|----------------|-----|
| Movie Facts 🎬 | ⭐⭐⭐⭐⭐ | High |
| Celebrity Secrets 🌟 | ⭐⭐⭐⭐⭐ | High |
| True Crime 🔍 | ⭐⭐⭐⭐⭐ | Very High |
| Sports Facts 🏆 | ⭐⭐⭐⭐ | Medium |
| Reddit Stories 💀 | ⭐⭐⭐⭐⭐ | High |

**Pro Tip:** Movie Facts + AI Voice + Screenshot Style = **Millions of views**

## 🛠️ Production Deployment (free, 24/7)

Want it online so you can open it from any device without keeping your PC on?
Deploy it to an **Oracle Cloud Always Free VM** — step-by-step guide here:

👉 **[deploy/DEPLOY_ORACLE.md](deploy/DEPLOY_ORACLE.md)**

Quick version (after creating the VM and uploading the project):

```bash
bash ~/shorts-generator/deploy/setup_server.sh   # installs ffmpeg + deps + 24/7 service
```

> Note: static/serverless hosts like **Vercel** and **Netlify** can't run this —
the app needs a real, always-on server with FFmpeg and a disk.

## 📊 Tech Stack

- **Frontend:** HTML/CSS/JS (can be replaced with Flutter)
- **Backend:** Python FastAPI
- **Video:** FFmpeg (5-10x faster than MoviePy)
- **AI:** Ollama + Llama 3 (local, no API key)
- **Subtitles:** faster-whisper (local)
- **Database:** SQLite (built-in)

## 💰 Cost: $0/month

No paid APIs needed:
- ✅ No OpenAI API
- ✅ No ElevenLabs
- ✅ No cloud services
- ✅ Everything runs locally

## 🔜 Future Features

- [ ] TikTok-style templates
- [ ] AI voiceover (local TTS)
- [ ] Auto thumbnail generation
- [ ] Batch processing
- [ ] Reddit story style
- [ ] Documentary style
- [ ] Faceless story videos
- [ ] Flutter mobile app

## 📄 License

MIT — Free for personal and commercial use.

---

Made with ❤️ for creators who want to go viral without spending a dime.
