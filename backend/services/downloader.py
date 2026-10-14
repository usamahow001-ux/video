"""
Video URL Downloader - fetch a video from a link using yt-dlp.

Supports YouTube (incl. Shorts), Instagram, TikTok, Facebook, X/Twitter and
1000+ other sites that yt-dlp supports. Downloads into the uploads/ folder so
the downloaded file flows through the exact same pipeline as a manual upload:
   crop  ->  generate_short()  ->  /api/download/{uid}

⚠️ Only download content you own or have the rights to use. Downloading
third-party videos may violate the source platform's Terms of Service.
"""

import os
import re
import glob
import socket
import struct
import ipaddress
from typing import Optional
from urllib.parse import urlparse

# Reuse the FFmpeg that the rest of the app already resolved/bundled.
# yt-dlp needs it to merge separate video+audio streams into one MP4.
from services.editor import FFMPEG_PATH

# ── Tunables ──
MAX_HEIGHT = 1080          # cap quality at 1080p (plenty for a 1080x1920 short)
MAX_DURATION_SECONDS = 900  # 15 min cap so we don't pull a whole movie
MAX_FILESIZE = 300 * 1024 * 1024  # hard 300 MB ceiling per download
DOWNLOAD_TIMEOUT = 20       # seconds for network socket ops

# Extensions yt-dlp may produce after merging
VIDEO_EXTS = (".mp4", ".mkv", ".webm", ".mov", ".m4v")


class DownloadError(Exception):
    """Raised when a URL cannot be downloaded (bad link, unsupported site, etc.)."""


def _ffmpeg_location() -> Optional[str]:
    """
    Tell yt-dlp where ffmpeg lives (it accepts either a directory or a file path).

    Priority:
      1. The app's own bundled binary: backend/ffmpeg_bin/ffmpeg.exe
      2. Whatever the rest of the app resolved (e.g. imageio-ffmpeg's build)
      3. None -> hope 'ffmpeg' is on PATH
    """
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bundled_dir = os.path.join(backend_dir, "ffmpeg_bin")
    for name in ("ffmpeg.exe", "ffmpeg"):
        if os.path.isfile(os.path.join(bundled_dir, name)):
            return bundled_dir

    if FFMPEG_PATH and FFMPEG_PATH.lower() != "ffmpeg" and os.path.exists(FFMPEG_PATH):
        return FFMPEG_PATH

    return None


def _is_private_ip(ip) -> bool:
    """True for loopback / private / link-local / reserved style addresses."""
    return bool(
        ip.is_loopback or ip.is_private or ip.is_link_local
        or ip.is_reserved or ip.is_multicast or ip.is_unspecified
    )


def _literal_ip(host: str):
    """
    Parse a host written as an IP, including the shorthand forms people use to
    dodge filters: decimal (2130706433), hex (0x7f000001), octal or partial
    (127.1). IPv6 literals are handled too. Returns None for real hostnames.
    """
    try:
        return ipaddress.IPv4Address(struct.unpack("!I", socket.inet_aton(host))[0])
    except (OSError, ValueError, struct.error):
        pass

    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def _resolves_to_private(host: str) -> bool:
    """
    True if the host resolves to a loopback/private/link-local address.

    Resolving (instead of just matching the literal text) is what stops tricks like
    http://2130706433/ (decimal 127.0.0.1), http://0x7f000001/ or public hostnames that
    point at localhost. This is a best-effort guard, not a full SSRF sandbox.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        # Can't resolve — let yt-dlp produce its own (clearer) error instead.
        return False

    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if _is_private_ip(ip):
            return True
    return False


def validate_url(url: str) -> str:
    """Sanity-check a user supplied URL. Returns the cleaned URL."""
    url = (url or "").strip().strip('"').strip("'")
    if not url:
        raise DownloadError("Please paste a video link first.")

    if len(url) > 2000:
        raise DownloadError("That link is too long.")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise DownloadError("Link must start with http:// or https://")

    if not parsed.netloc:
        raise DownloadError("That doesn't look like a valid link.")

    # This runs server-side, so refuse anything aimed at the local network.
    host = parsed.hostname or ""
    literal = _literal_ip(host) if host else None
    if (
        not host
        or host.lower() in ("localhost", "localhost.localdomain")
        or host.lower().endswith((".local", ".internal", ".localhost"))
        or (literal is not None and _is_private_ip(literal))
        or _resolves_to_private(host)
    ):
        raise DownloadError("Local network links are not allowed.")

    return url


def _yt_dlp_format(max_height: int) -> str:
    """Prefer an MP4 (video+audio) combo at or below max_height, else fall back gracefully."""
    h = max(240, min(int(max_height or MAX_HEIGHT), MAX_HEIGHT))
    return (
        f"bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/"
        f"bestvideo[height<={h}]+bestaudio/"
        f"best[height<={h}]/"
        f"bestvideo+bestaudio/best"
    )


def _match_filter(info: dict, *, incomplete: bool = False):
    """
    Let yt-dlp reject videos BEFORE downloading them (bandwidth/disk saver).
    Returning a string means "skip this video with this reason".
    """
    if incomplete:
        return None  # duration unknown during playlist/metadata probing
    duration = info.get("duration")
    if duration and duration > MAX_DURATION_SECONDS:
        return f"Longer than {MAX_DURATION_SECONDS // 60} minutes"
    return None


def _cleanup_partials(out_tmpl: str) -> None:
    """Remove leftover .part / .ytdl fragments from a failed download."""
    stem = re.sub(r"%\(ext\)s$", "", out_tmpl)
    for path in glob.glob(stem + "*"):
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass


def download_video(url: str, output_dir: str, uid: str, max_height: int = MAX_HEIGHT) -> dict:
    """
    Download a video from `url` into `output_dir` as `{uid}.mp4` (or .mkv/.webm).

    Returns a dict with uid, filename, path, title, duration, width, height, filesize.
    Raises DownloadError with a human friendly message on failure.
    """
    try:
        import yt_dlp
    except ImportError:
        raise DownloadError(
            "yt-dlp is not installed. Run: pip install yt-dlp"
        )

    url = validate_url(url)
    os.makedirs(output_dir, exist_ok=True)

    out_tmpl = os.path.join(output_dir, f"{uid}.%(ext)s")

    ydl_opts = {
        "format": _yt_dlp_format(max_height),
        "merge_output_format": "mp4",
        "outtmpl": out_tmpl,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,        # a channel/playlist link must not pull the whole list
        "playlist_items": "1",
        "restrictfilenames": True,
        "socket_timeout": DOWNLOAD_TIMEOUT,
        "retries": 2,
        "overwrites": True,
        "max_filesize": MAX_FILESIZE,
        "match_filter": _match_filter,
        # Be a good citizen + reduce the chance of bot checks
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        },
        # Use Android/iOS player clients for YouTube to bypass bot checks (429 / Sign in to confirm you're not a bot)
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios"],
            }
        },
    }

    # If user dropped a cookies.txt in backend/, use it
    cookie_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cookies.txt")
    if os.path.isfile(cookie_file):
        ydl_opts["cookiefile"] = cookie_file

    ffmpeg_location = _ffmpeg_location()
    if ffmpeg_location:
        ydl_opts["ffmpeg_location"] = ffmpeg_location

    info: dict = {}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as e:
        _cleanup_partials(out_tmpl)
        raise DownloadError(_friendly_error(str(e)))
    except Exception as e:  # pragma: no cover - defensive
        _cleanup_partials(out_tmpl)
        raise DownloadError(f"Download failed: {e}")

    if info and "entries" in info:  # playlist link -> take the first entry
        info = (info.get("entries") or [{}])[0] or {}

    # Locate the freshly downloaded file
    candidates = [
        p for ext in VIDEO_EXTS
        for p in [os.path.join(output_dir, f"{uid}{ext}")]
        if os.path.exists(p)
    ]
    if not candidates:
        # Fallback: any file starting with the uid
        candidates = sorted(glob.glob(os.path.join(output_dir, f"{uid}.*")))
        candidates = [c for c in candidates if c.lower().endswith(VIDEO_EXTS)]

    if not candidates:
        _cleanup_partials(out_tmpl)
        raise DownloadError("Downloaded file not found. The link may point to an image or an unsupported post.")

    path = max(candidates, key=os.path.getsize)
    size = os.path.getsize(path)

    if size < 10 * 1024:  # <10 KB is not a real video
        try:
            os.remove(path)
        except OSError:
            pass
        raise DownloadError("That link didn't return a usable video file.")

    duration = float(info.get("duration") or 0)
    if duration and duration > MAX_DURATION_SECONDS:
        try:
            os.remove(path)
        except OSError:
            pass
        raise DownloadError(
            f"Video is {int(duration // 60)}m {int(duration % 60)}s long — "
            f"keep it under {MAX_DURATION_SECONDS // 60} minutes for Shorts."
        )

    print(f"[DOWNLOAD] {info.get('title') or url} -> {os.path.basename(path)} ({size / 1048576:.1f} MB)")

    return {
        "uid": uid,
        "filename": os.path.basename(path),
        "path": path,
        "title": info.get("title") or "video",
        "uploader": info.get("uploader") or info.get("channel") or "",
        "webpage_url": info.get("webpage_url") or url,
        "duration": duration,
        "width": int(info.get("width") or 0),
        "height": int(info.get("height") or 0),
        "filesize": size,
        "ext": os.path.splitext(path)[1].lstrip(".").lower(),
    }


def _friendly_error(raw: str) -> str:
    """Turn yt-dlp's verbose errors into something a user can act on."""
    msg = raw.strip().split("\n")[0]
    low = raw.lower()

    if "not a valid url" in low or "unsupported url" in low:
        return "That link isn't supported. Try a YouTube, Shorts, Instagram or TikTok video link."
    if "bot" in low:
        return "YouTube is blocking automated requests (bot verification). Try another link or download & upload the video file directly."
    if "private" in low:
        return "This video is private — the server can't access it."
    if "sign in" in low or "login" in low or "cookies" in low:
        return "This video requires login — the server can't access it without authentication."
    if "unavailable" in low or "removed" in low or "no longer" in low:
        return "That video is unavailable or has been removed."
    if "age" in low and "confirm" in low:
        return "That video is age-restricted and can't be downloaded without login."
    if "longer than" in low:
        return f"That video is longer than {MAX_DURATION_SECONDS // 60} minutes — pick a shorter clip."
    if "max-filesize" in low or "larger than" in low:
        return f"That video is over {MAX_FILESIZE // (1024 * 1024)} MB — try a shorter clip."
    if "timed out" in low or "timeout" in low:
        return "Download timed out. Check your internet connection and try again."
    if "unable to download" in low or "urlopen error" in low or "getaddrinfo" in low:
        return "Couldn't reach that site. Check the link and your internet connection."

    # Strip yt-dlp's "ERROR: " prefix + trailing noise
    msg = re.sub(r"^ERROR:\s*", "", msg)
    msg = re.sub(r"\s*; please report this issue.*$", "", msg, flags=re.IGNORECASE)
    return msg[:300] or "Download failed. Please try a different link."


__all__ = [
    "DownloadError",
    "download_video",
    "validate_url",
    "MAX_HEIGHT",
]
