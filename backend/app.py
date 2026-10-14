"""
AI Shorts Generator - FastAPI Backend Server
Complete free, local video editing tool with AI-powered viral hook generation
"""

import os
import re
import sys
import uuid
import socket
import shutil
import threading
import mimetypes
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

# ── Fix Windows console encoding ──
# Windows defaults stdout to cp1252 ("charmap"), which crashes on emoji like 😱
# that appear in viral hooks and story text. Force UTF-8 so emoji never crash
# the server. errors="replace" is a safety net for any unencodable character.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

import hmac
import hashlib
import time
from collections import defaultdict, deque
from urllib.parse import quote

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool

# Import services
from services.editor import generate_short
from services.ai import rewrite_story, generate_seo
from services.subtitle import generate_srt
from services.template import get_template_names, get_template_for_story
# NOTE: imported as a module so it can't clash with the /api/download route handler
# (which is also called download_video).
from services import downloader as video_downloader
import database

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend")
FFMPEG_BIN = os.path.join(BASE_DIR, "ffmpeg_bin")

# ── Authentication (single shared password) ──
# One password protects the whole app. Set APP_PASSWORD (and ideally SECRET_KEY)
# as environment variables. On the server these live in /etc/shorts-generator.env.
DEFAULT_PASSWORD = "Pass@123"
APP_PASSWORD = os.environ.get("APP_PASSWORD") or DEFAULT_PASSWORD
SESSION_SECRET = os.environ.get("SECRET_KEY") or f"shorts-generator-session::{APP_PASSWORD}::v1"


def _int_env(name: str, default: int) -> int:
    """Read an int env var, falling back to `default` if unset or malformed."""
    try:
        return int(os.environ.get(name) or default)
    except (TypeError, ValueError):
        return default


SESSION_TTL = _int_env("SESSION_TTL_SECONDS", 60 * 60 * 24 * 7)  # 7 days
COOKIE_NAME = "shorts_auth"
# Only send the cookie over HTTPS. Enable with COOKIE_SECURE=1 behind HTTPS/Caddy or auto-detected on HF Spaces.
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "").strip().lower() in {"1", "true", "yes", "on"} or bool(os.environ.get("SPACE_ID"))

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Import FFmpeg detection from editor (shared utility)
from services.editor import FFMPEG_PATH


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    print("[STARTUP] AI Shorts Generator starting up...")
    print(f"[UPLOADS] {os.path.abspath(UPLOAD_DIR)}")
    print(f"[OUTPUT] {os.path.abspath(OUTPUT_DIR)}")
    print(f"[FRONTEND] {os.path.abspath(FRONTEND_DIR)}")
    if APP_PASSWORD == "changeme":
        print("[AUTH] WARNING: using the default password 'changeme'. Set APP_PASSWORD to change it.")
    else:
        print("[AUTH] Password protection is ON.")
    
    # Check FFmpeg
    import subprocess
    try:
        result = subprocess.run([FFMPEG_PATH, "-version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version = result.stdout.split("\n")[0] if result.stdout else "unknown"
            print(f"[FFMPEG] {version}")
        else:
            print("[WARN] FFmpeg check failed")
    except Exception as e:
        print(f"[WARN] FFmpeg check failed: {e}")
    
    yield
    
    print("[SHUTDOWN] Shutting down...")


app = FastAPI(
    title="AI Shorts Generator",
    description="Generate viral YouTube Shorts from uploaded videos and stories",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════
# Authentication — simple shared password
# ═══════════════════════════════════════

def _sign(value: str) -> str:
    """HMAC-SHA256 signature for a session value."""
    return hmac.new(SESSION_SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()


def make_session_token() -> str:
    """Create a signed token that expires after SESSION_TTL seconds."""
    expires = str(int(time.time()) + SESSION_TTL)
    return f"{expires}.{_sign(expires)}"


def verify_session_token(token: str) -> bool:
    """True only if the token is well-formed, correctly signed and unexpired."""
    if not token or "." not in token:
        return False
    expires, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(signature, _sign(expires)):
        return False
    try:
        return int(expires) > time.time()
    except ValueError:
        return False


def verify_password(candidate: str) -> bool:
    """Constant-time password check."""
    return hmac.compare_digest((candidate or "").encode(), APP_PASSWORD.encode())


def is_authenticated(request: Request) -> bool:
    """True if the request carries a valid session cookie."""
    return verify_session_token(request.cookies.get(COOKIE_NAME, ""))


# Lightweight brute-force guard for the login endpoint (in-memory, per client IP)
MAX_LOGIN_ATTEMPTS = 8
LOGIN_WINDOW_SECONDS = 300
_failed_logins: "defaultdict[str, deque]" = defaultdict(deque)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _too_many_attempts(ip: str) -> bool:
    """True if this IP made too many recent failed attempts."""
    attempts = _failed_logins[ip]
    cutoff = time.time() - LOGIN_WINDOW_SECONDS
    while attempts and attempts[0] < cutoff:
        attempts.popleft()
    return len(attempts) >= MAX_LOGIN_ATTEMPTS


# Endpoints that must stay reachable without a session (the login flow)
PUBLIC_PATHS = {"/login", "/api/login"}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Require a valid session for every route except the login flow."""
    path = request.url.path

    # CORS preflight and the login page/endpoint are always allowed through
    if request.method == "OPTIONS" or path.rstrip("/") in PUBLIC_PATHS:
        return await call_next(request)

    if is_authenticated(request):
        return await call_next(request)

    # API and docs callers get a clean 401; browsers are sent to the login page
    if path.startswith("/api/") or path.startswith(("/docs", "/redoc")) or path == "/openapi.json":
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)

    return RedirectResponse(url=f"/login?next={quote(path, safe='')}", status_code=303)


LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sign in \u2022 AI Shorts Generator</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#07070d; --text:#eeeef5; --secondary:#9999bb; --muted:#555577;
    --accent:#7c5cfc; --error:#ef4444; --border:rgba(60,60,90,.3);
  }
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--text);
    min-height:100vh;display:flex;align-items:center;justify-content:center;overflow:hidden;padding:20px}
  .orb{position:fixed;border-radius:50%;filter:blur(80px);opacity:.45;pointer-events:none}
  .orb1{width:480px;height:480px;background:radial-gradient(circle,rgba(124,92,252,.35),transparent 70%);top:-12%;left:-6%}
  .orb2{width:380px;height:380px;background:radial-gradient(circle,rgba(167,139,250,.25),transparent 70%);bottom:-10%;right:-6%}
  .card{position:relative;z-index:1;width:100%;max-width:400px;padding:40px 34px;
    background:rgba(20,20,40,.6);border:1px solid var(--border);border-radius:26px;
    backdrop-filter:blur(20px);box-shadow:0 20px 60px rgba(0,0,0,.55);text-align:center;
    animation:rise .5s cubic-bezier(.34,1.56,.64,1)}
  @keyframes rise{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:translateY(0)}}
  .logo{font-size:44px;margin-bottom:10px;animation:float 3.5s ease-in-out infinite}
  @keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
  h1{font-size:23px;font-weight:800;background:linear-gradient(135deg,#6d28d9,#a78bfa,#c084fc);
    -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:6px}
  p.sub{font-size:13px;color:var(--muted);margin-bottom:26px}
  .field{position:relative;text-align:left;margin-bottom:14px}
  .field label{display:block;font-size:12px;font-weight:600;color:var(--secondary);margin-bottom:7px}
  .input-wrap{position:relative;display:flex;align-items:center}
  .input-wrap .icon{position:absolute;left:14px;font-size:14px;opacity:.65;pointer-events:none}
  .input-wrap input{width:100%;padding:13px 44px 13px 40px;background:rgba(25,25,50,.8);
    border:1px solid var(--border);border-radius:12px;color:var(--text);font-family:inherit;font-size:14px;transition:all .3s}
  .input-wrap input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px rgba(124,92,252,.15)}
  .toggle{position:absolute;right:8px;background:none;border:none;color:var(--muted);cursor:pointer;
    font-size:15px;padding:6px 8px;border-radius:8px}
  .toggle:hover{color:var(--secondary);background:rgba(255,255,255,.05)}
  .error{min-height:18px;font-size:12.5px;color:var(--error);text-align:left;margin-bottom:12px;font-weight:500}
  button.submit{width:100%;padding:14px;border:none;border-radius:12px;color:#fff;font-family:inherit;
    font-size:15px;font-weight:700;cursor:pointer;background:linear-gradient(135deg,#7c5cfc,#a78bfa);transition:all .3s}
  button.submit:hover:not(:disabled){transform:translateY(-2px);box-shadow:0 10px 30px rgba(124,92,252,.4)}
  button.submit:disabled{opacity:.6;cursor:not-allowed}
  .spinner{display:none;width:16px;height:16px;border:2px solid rgba(255,255,255,.35);border-top-color:#fff;
    border-radius:50%;animation:spin .7s linear infinite;vertical-align:-3px;margin-right:8px}
  @keyframes spin{to{transform:rotate(360deg)}}
  button.submit.loading .spinner{display:inline-block}
  .foot{margin-top:20px;font-size:11px;color:var(--muted)}
</style>
</head>
<body>
  <div class="orb orb1"></div><div class="orb orb2"></div>
  <div class="card">
    <div class="logo">\U0001F3AC</div>
    <h1>AI Shorts Generator</h1>
    <p class="sub">Enter the password to continue</p>
    <form id="loginForm" autocomplete="off">
      <div class="field">
        <label for="password">Password</label>
        <div class="input-wrap">
          <span class="icon">\U0001F512</span>
          <input type="password" id="password" placeholder="Enter password" autocomplete="current-password" required autofocus>
          <button type="button" class="toggle" id="toggle" title="Show password">\U0001F441</button>
        </div>
      </div>
      <div class="error" id="error"></div>
      <button type="submit" class="submit" id="submitBtn">
        <span class="spinner"></span><span id="submitText">Unlock</span>
      </button>
    </form>
    <div class="foot">\U0001F510 Access is restricted to people with the password.</div>
  </div>
  <script>
    var form = document.getElementById('loginForm');
    var input = document.getElementById('password');
    var errorEl = document.getElementById('error');
    var btn = document.getElementById('submitBtn');
    var toggle = document.getElementById('toggle');
    toggle.addEventListener('click', function(){
      var isPw = input.type === 'password';
      input.type = isPw ? 'text' : 'password';
      toggle.textContent = isPw ? '\U0001F648' : '\U0001F441';
      toggle.title = isPw ? 'Hide password' : 'Show password';
      input.focus();
    });
    function nextUrl(){
      var p = new URLSearchParams(location.search).get('next');
      return (p && p.charAt(0) === '/' && p.charAt(1) !== '/') ? p : '/';
    }
    form.addEventListener('submit', async function(e){
      e.preventDefault();
      errorEl.textContent = '';
      btn.disabled = true;
      btn.classList.add('loading');
      try {
        var res = await fetch('/api/login', {
          method: 'POST',
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          body: new URLSearchParams({password: input.value})
        });
        if (res.ok) { location.href = nextUrl(); return; }
        var data = await res.json().catch(function(){ return {}; });
        errorEl.textContent = data.detail || 'Incorrect password. Try again.';
        input.value = '';
        input.focus();
      } catch (err) {
        errorEl.textContent = 'Could not reach the server. Please try again.';
      } finally {
        btn.disabled = false;
        btn.classList.remove('loading');
      }
    });
  </script>
</body>
</html>"""


@app.get("/login")
async def login_page(request: Request):
    """Show the login screen (or bounce straight to the app if already signed in)."""
    if is_authenticated(request):
        return RedirectResponse(url="/", status_code=303)
    return HTMLResponse(LOGIN_PAGE)


@app.post("/api/login")
async def login(request: Request, password: str = Form(...)):
    """Check the shared password and set a signed session cookie."""
    ip = _client_ip(request)
    if _too_many_attempts(ip):
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Please wait a few minutes and try again.",
        )
    if not verify_password(password):
        _failed_logins[ip].append(time.time())
        raise HTTPException(status_code=401, detail="Incorrect password. Try again.")
    samesite_setting = "none" if (COOKIE_SECURE or os.environ.get("SPACE_ID")) else "lax"
    response = JSONResponse({"status": "ok"})
    response.set_cookie(
        key=COOKIE_NAME,
        value=make_session_token(),
        max_age=SESSION_TTL,
        httponly=True,
        samesite=samesite_setting,
        secure=COOKIE_SECURE,
        path="/",
    )
    return response


@app.post("/api/logout")
async def logout():
    """Clear the session cookie."""
    response = JSONResponse({"status": "ok"})
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


# ═══════════════════════════════════════
# API Routes (defined BEFORE static mount)
# ═══════════════════════════════════════

@app.get("/api/status")
async def get_status():
    """Check if server is running and all dependencies are available"""
    import subprocess
    
    # Check FFmpeg
    ffmpeg_available = False
    try:
        result = subprocess.run([FFMPEG_PATH, "-version"], capture_output=True, text=True, timeout=5)
        ffmpeg_available = result.returncode == 0
    except:
        pass
    
    # Check Ollama
    ollama_available = False
    try:
        import requests
        result = requests.get("http://localhost:11434/api/tags", timeout=2)
        ollama_available = result.status_code == 200
    except:
        pass
    
    # Check Whisper
    whisper_available = False
    try:
        import faster_whisper
        whisper_available = True
    except:
        pass
    
    # Check yt-dlp (used for "paste a link" video downloads)
    downloader_available = False
    try:
        import yt_dlp
        downloader_available = True
    except:
        pass
    
    return {
        "status": "running",
        "ffmpeg": ffmpeg_available,
        "ollama": ollama_available,
        "whisper": whisper_available,
        "downloader": downloader_available,
        "version": "1.0.0",
    }


# Extensions accepted for source videos (uploads + URL downloads).
# Tuple (not set) so the lookup in /api/uploads/{uid} has a stable order.
ALLOWED_VIDEO_EXTS = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v')


@app.get("/api/templates")
async def get_templates():
    """Get available templates"""
    return {"templates": get_template_names()}


@app.post("/api/fetch-url")
async def fetch_url(
    url: str = Form(...),
    max_height: Optional[int] = Form(1080),
):
    """
    Download a video from a link (YouTube / YouTube Shorts / Instagram / TikTok ...)
    into the uploads folder, ready to be cropped and turned into a Short.

    Returns a preview URL the browser can load directly, so the existing crop
    modal and generate pipeline work on the downloaded video unchanged.
    """
    if not url or not url.strip():
        raise HTTPException(status_code=400, detail="Please paste a video link")

    uid = uuid.uuid4().hex[:12]

    try:
        # Downloading is blocking (network + ffmpeg merge) so keep it off the event loop
        result = await run_in_threadpool(
            video_downloader.download_video,
            url.strip(),
            UPLOAD_DIR,
            uid,
            max_height or 1080,
        )
    except video_downloader.DownloadError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[ERROR] URL download failed: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {e}")

    return {
        "status": "success",
        "uid": uid,
        "filename": result["filename"],
        "preview_url": f"/api/uploads/{uid}",
        "title": result["title"],
        "uploader": result["uploader"],
        "source_url": result["webpage_url"],
        "duration": round(result["duration"], 1),
        "width": result["width"],
        "height": result["height"],
        "file_size": result["filesize"],
    }


@app.get("/api/uploads/{uid}")
async def get_uploaded_source(uid: str):
    """
    Serve a source video (uploaded or downloaded from a URL) so the browser can
    preview it and run the crop tool on it.

    Note: like the rest of this local tool, this endpoint is unauthenticated —
    it only guards against path traversal via the id pattern below.
    """
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,40}", uid or ""):
        raise HTTPException(status_code=400, detail="Invalid video id")

    for ext in ALLOWED_VIDEO_EXTS:
        path = os.path.join(UPLOAD_DIR, f"{uid}{ext}")
        if os.path.exists(path):
            media_type = mimetypes.guess_type(path)[0] or "video/mp4"
            return FileResponse(path, media_type=media_type)

    raise HTTPException(status_code=404, detail="Source video not found")


@app.post("/api/rewrite")
async def rewrite(story: str = Form(...)):
    """Rewrite a story into a viral hook using AI"""
    try:
        result = rewrite_story(story)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate")
async def generate(
    video: UploadFile = File(...),
    story: str = Form(...),
    template: Optional[str] = Form("evergreen"),
    channel_name: Optional[str] = Form("YourChannel"),
    channel_handle: Optional[str] = Form("@yourchannel"),
    logo: Optional[UploadFile] = File(None),
    background: Optional[UploadFile] = File(None),
    add_subtitles: Optional[bool] = Form(False),
    audio_pitch_shift: Optional[bool] = Form(False),
    video_fit_mode: Optional[str] = Form("fit"),
    crop_x: Optional[int] = Form(None),
    crop_y: Optional[int] = Form(None),
    crop_w: Optional[int] = Form(None),
    crop_h: Optional[int] = Form(None),
    crop_rotated: Optional[str] = Form("0"),
    niche_text: Optional[str] = Form(None),
):
    """
    Generate a viral Short from uploaded video and story text.
    Supports channel branding and logo upload.
    """
    try:
        # Validate inputs
        if not video.filename:
            raise HTTPException(status_code=400, detail="No video file provided")
        
        if not story or len(story.strip()) < 3:
            raise HTTPException(status_code=400, detail="Story text too short")
        
        # Validate video file type
        file_ext = os.path.splitext(video.filename)[1].lower()
        if file_ext not in ALLOWED_VIDEO_EXTS:
            raise HTTPException(status_code=400, detail=f"Invalid video type: {file_ext}")
        
        # Save uploaded video
        uid = uuid.uuid4().hex[:12]
        safe_video = f"{uid}{file_ext}"
        video_path = os.path.join(UPLOAD_DIR, safe_video)
        
        with open(video_path, "wb") as f:
            content = await video.read()
            f.write(content)
        
        file_size_mb = len(content) / (1024 * 1024)
        print(f"[UPLOAD] {video.filename} ({file_size_mb:.1f} MB)")
        
        # Save logo if provided
        logo_path = None
        if logo and logo.filename:
            logo_ext = os.path.splitext(logo.filename)[1].lower()
            if logo_ext in {'.png', '.jpg', '.jpeg', '.webp'}:
                safe_logo = f"logo_{uid}{logo_ext}"
                logo_path = os.path.join(UPLOAD_DIR, safe_logo)
                with open(logo_path, "wb") as f:
                    f.write(await logo.read())
                print(f"[LOGO] Saved: {logo.filename}")
        
        # Save background if provided
        bg_path = None
        if background and background.filename:
            bg_ext = os.path.splitext(background.filename)[1].lower()
            allowed_bg = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.mp4', '.mov', '.avi', '.mkv'}
            if bg_ext in allowed_bg:
                safe_bg = f"bg_{uid}{bg_ext}"
                bg_path = os.path.join(UPLOAD_DIR, safe_bg)
                with open(bg_path, "wb") as f:
                    f.write(await background.read())
                print(f"[BG] Saved: {background.filename}")
        
        # Generate viral hook
        ai_result = rewrite_story(story)
        hook = ai_result.get("hook", story[:100])
        niche = ai_result.get("niche", "general")
        hashtags = ai_result.get("hashtags", "#shorts #viral")
        
        print(f"[AI HOOK] {hook}")
        print(f"[NICHE] {niche}")
        
        # Kick off SEO metadata generation in the background so it overlaps with
        # video rendering — the user only waits for the slower of the two.
        seo_result = {}
        
        def _generate_seo():
            try:
                seo_result.update(generate_seo(story, hook=hook, niche=niche))
                print(f"[SEO] Title: {seo_result.get('title', '')}")
            except Exception as seo_err:
                print(f"[SEO] Generation failed: {seo_err}")
        
        seo_thread = threading.Thread(target=_generate_seo, daemon=True)
        seo_thread.start()
        
        # Generate the Short video
        output_path = os.path.join(OUTPUT_DIR, f"short_{uid}.mp4")
        
        result_path = generate_short(
            video_path=video_path,
            story_text=story,
            hook_text=hook,
            channel_name=channel_name or "YourChannel",
            channel_handle=channel_handle or "@yourchannel",
            logo_path=logo_path,
            bg_path=bg_path,
            template_name=template or "evergreen",
            output_path=output_path,
            add_subtitles=add_subtitles or False,
            audio_pitch_shift=audio_pitch_shift or False,
            crop={"x": crop_x, "y": crop_y, "w": crop_w, "h": crop_h} if all(v is not None for v in [crop_x, crop_y, crop_w, crop_h]) else None,
            crop_rotated=crop_rotated == "1",
            video_fit_mode=video_fit_mode or "fit",
            niche_text=niche_text
        )
        
        if not result_path or not os.path.exists(result_path):
            raise HTTPException(status_code=500, detail="Video generation failed")
        
        # Get file info
        file_size = os.path.getsize(result_path)
        duration = 0
        try:
            try:
                from moviepy.editor import VideoFileClip  # moviepy 1.x
            except ImportError:
                from moviepy import VideoFileClip  # moviepy 2.x
            with VideoFileClip(result_path) as clip:
                duration = clip.duration
        except:
            pass
        
        # Save to database
        database.save_export(
            video_name=video.filename,
            story_text=story,
            hook_text=hook,
            template_name=template or "Evergreen",
            niche=niche,
            output_path=result_path,
            duration=duration,
            file_size=file_size,
            uid=uid,
        )
        
        print(f"[SUCCESS] Short generated: {result_path}")
        
        # Video is ready — wait for the SEO thread (usually already finished
        # while rendering) so the frontend gets the full SEO pack.
        seo_thread.join()
        seo = seo_result or {
            "title": hook[:95],
            "description": story,
            "hashtags": hashtags,
            "tags": "shorts, viral, storytime",
        }
        
        return {
            "status": "success",
            "video_url": f"/api/download/{uid}",
            "filename": f"short_{uid}.mp4",
            "hook": hook,
            "niche": niche,
            "hashtags": hashtags,
            "seo": seo,
            "duration": round(duration, 1),
            "file_size": file_size,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/download/{uid}")
async def download_video(uid: str):
    """Download a generated Short video"""
    video_path = os.path.join(OUTPUT_DIR, f"short_{uid}.mp4")
    
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video not found")
    
    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=f"short_{uid}.mp4",
        headers={
            "Content-Disposition": f'attachment; filename="short_{uid}.mp4"'
        }
    )


@app.get("/api/exports")
async def get_exports(limit: int = 20, offset: int = 0):
    """Get list of generated exports"""
    exports = database.get_exports(limit=limit, offset=offset)
    return {"exports": exports, "total": len(exports)}


@app.get("/api/exports/{export_id}")
async def get_export(export_id: int):
    """Get a single export details"""
    export = database.get_export(export_id)
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")
    return export


@app.get("/api/stats")
async def get_stats():
    """Get dashboard statistics"""
    return database.get_statistics()


@app.get("/api/niches")
async def get_niches():
    """Get recommended niches for viral content"""
    niches = [
        {
            "name": "Movie Facts",
            "description": "Behind-the-scenes movie secrets & actor stories",
            "viral_potential": "5/5",
            "rpm": "High",
            "example": "Did you know this actor almost quit the movie?"
        },
        {
            "name": "Celebrity Secrets",
            "description": "Unknown facts about famous celebrities",
            "viral_potential": "5/5",
            "rpm": "High",
            "example": "Nobody expected this celebrity secret..."
        },
        {
            "name": "True Crime",
            "description": "Mysterious crime stories and investigations",
            "viral_potential": "5/5",
            "rpm": "Very High",
            "example": "The detective noticed ONE thing that broke the case"
        },
        {
            "name": "Sports Facts",
            "description": "Incredible sports moments and athlete stories",
            "viral_potential": "4/5",
            "rpm": "Medium",
            "example": "This athlete's comeback was UNREAL"
        },
        {
            "name": "Reddit Stories",
            "description": "Viral Reddit stories narrated over gameplay",
            "viral_potential": "5/5",
            "rpm": "High",
            "example": "This Reddit story went viral for a reason..."
        },
        {
            "name": "Documentary Facts",
            "description": "Interesting facts from documentaries",
            "viral_potential": "4/5",
            "rpm": "Medium",
            "example": "Scientists were SHOCKED by this discovery"
        },
    ]
    return {"niches": niches}


# ═══════════════════════════════════════
# Static file mount (serves frontend)
# ═══════════════════════════════════════
# Mount AFTER API routes so API takes priority
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    print(f"[FRONTEND] Serving from {FRONTEND_DIR}")
else:
    print(f"[WARN] Frontend not found at {FRONTEND_DIR}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860 if os.environ.get("SPACE_ID") else 8000))
    print("=" * 50)
    print("AI Shorts Generator")
    print("=" * 50)
    print("Starting server...")
    print(f"Frontend: http://localhost:{port}")
    print(f"API Docs: http://localhost:{port}/docs")
    print("=" * 50)
    print("")
    # Check if port is in use first (skip when in cloud container)
    if not os.environ.get("SPACE_ID"):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        if result == 0:
            print(f"[ERROR] Port {port} is already in use!")
            print(f"        Try: netstat -ano | findstr :{port}")
            print("        To kill: taskkill /PID <PID> /F")
            sock.close()
            exit(1)
        sock.close()
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
