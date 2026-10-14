"""
Video Editor Service - Core video processing using FFmpeg
Now uses Pillow for text rendering (avoids FFmpeg fontconfig crash on Windows)
"""

import os
import uuid
import subprocess
from typing import Optional, List, Tuple

from PIL import Image, ImageDraw, ImageFont

from services.template import LayoutConfig, assign_text_colors


# Global FFmpeg path - set once and reused
FFMPEG_PATH: str = "ffmpeg"

def _find_ffmpeg() -> str:
    """Find the FFmpeg executable path. Returns 'ffmpeg' as default if not found."""
    import shutil
    import glob
    # First try PATH
    path_found = shutil.which("ffmpeg")
    if path_found:
        return path_found
    # Try imageio_ffmpeg (bundled binary) - handles version detection automatically
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass
    # Try glob search for any imageio_ffmpeg binary (works with any Python version)
    pattern = os.path.expanduser(r"~\AppData\Roaming\Python\Python3*\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-*.exe")
    matches = glob.glob(pattern)
    if matches:
        return matches[0]
    return "ffmpeg"  # fallback


# Initialize FFmpeg path on module load
FFMPEG_PATH = _find_ffmpeg()
print(f"[FFMPEG] Using: {FFMPEG_PATH}")


class VideoEditor:
    """Main video editing engine - uses Pillow for text + FFmpeg for video"""
    
    def __init__(self, assets_dir: str = "assets"):
        self.assets_dir = assets_dir
        self.output_dir = "output"
        self.uploads_dir = "uploads"
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.uploads_dir, exist_ok=True)
    
    def _run_ffmpeg(self, cmd: str, description: str = "") -> bool:
        """Run an FFmpeg command. Replaces 'ffmpeg ' prefix with the full FFmpeg path."""
        try:
            # Replace first 'ffmpeg' reference with full path
            if cmd.startswith("ffmpeg "):
                cmd = cmd.replace("ffmpeg ", f'"{FFMPEG_PATH}" ', 1)
            elif cmd.startswith("ffmpeg"):
                cmd = cmd.replace("ffmpeg", f'"{FFMPEG_PATH}"', 1)
            
            print(f"[FFMPEG] {description}...")
            result = subprocess.run(
                cmd, shell=True, check=True,
                capture_output=True, text=True, timeout=300
            )
            print(f"[DONE] {description}")
            return True
        except subprocess.CalledProcessError as e:
            err = e.stderr[:500] if e.stderr else "No error output"
            print(f"[FFMPEG ERROR] {err}")
            return False
        except subprocess.TimeoutExpired:
            print("[FFMPEG ERROR] Timed out")
            return False
        except Exception as e:
            print(f"[ERROR] {e}")
            return False
    
    def _cleanup(self, files: list):
        for f in files:
            if os.path.exists(f):
                try: os.remove(f)
                except: pass
    
    # Fonts tried in order. Linux paths come first so the Oracle Cloud (Ubuntu)
    # deployment renders readable text instead of silently falling back to a
    # tiny bitmap font. Windows/macOS paths keep local dev unchanged.
    _FONT_CANDIDATES = (
        # Linux - Debian/Ubuntu (fonts-dejavu-core / fonts-liberation)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        # macOS
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        # Windows
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/Arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/consola.ttf",
    )

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Get a bold font at the specified size (cross-platform)."""
        for fp in self._FONT_CANDIDATES:
            if os.path.exists(fp):
                try:
                    return ImageFont.truetype(fp, size)
                except Exception:
                    continue
        # Last resort. Pillow >= 10.1 can scale its built-in font; older versions
        # ignore the size and return a tiny bitmap font.
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()
    
    def compose_evergreen_short(
        self,
        video_path: str,
        story_text: str,
        channel_name: str = "YourChannel",
        channel_handle: str = "@yourchannel",
        logo_path: Optional[str] = None,
        bg_path: Optional[str] = None,
        template: LayoutConfig = None,
        output_path: str = None,
        add_subtitles: bool = False,
        crop: Optional[dict] = None,
        crop_rotated: bool = False,
        video_fit_mode: str = "fit",
        audio_pitch_shift: bool = False,
        niche_text: Optional[str] = None,
        hook_text: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate Short using: Pillow for text images + FFmpeg for video.
        This avoids the fontconfig crash in FFmpeg essentials build.
        
        Layout:
        [BORDER]  [LOGO] Channel Name    [BORDER]
        [BORDER]         @handle         [BORDER]
        [BORDER]  Colored Story Text     [BORDER]
        [BORDER]  +----VIDEO---------+  [BORDER]
        [BORDER]  |                  |  [BORDER]
        [BORDER]  +------------------+  [BORDER]
        [BORDER]    @channel_handle     [BORDER]
        """
        if template is None:
            from services.template import TEMPLATES
            template = TEMPLATES.get("evergreen")
        
        W, H = template.width, template.height
        B = template.border_width
        
        if output_path is None:
            uid = uuid.uuid4().hex[:12]
            output_path = os.path.join(self.output_dir, f"short_{uid}.mp4")
        
        # Get video duration
        try:
            try:
                from moviepy.editor import VideoFileClip  # moviepy 1.x
            except ImportError:
                from moviepy import VideoFileClip  # moviepy 2.x
            with VideoFileClip(video_path) as clip:
                duration = clip.duration
        except:
            duration = 30
        
        uid = uuid.uuid4().hex[:8]
        temp_files = []
        
        # === STEP 0: Crop video if coordinates provided ===
        input_video = video_path
        crop_applied = False
        if crop and all(k in crop for k in ("x", "y", "w", "h")):
            try:
                cx, cy, cw, ch = int(crop["x"]), int(crop["y"]), int(crop["w"]), int(crop["h"])
                if cw > 10 and ch > 10:
                    cropped_path = os.path.join(self.output_dir, f"t_cropped_{uid}.mp4")
                    temp_files.append(cropped_path)
                    
                    # 💡 NEW APPROACH: Use autorotate FIRST, then crop.
                    # The frontend sends crop coordinates in DISPLAY (correctly oriented) space.
                    # For portrait phone videos stored as landscape with rotation metadata:
                    # - autorotate reads the rotation metadata and rotates the video correctly
                    # - THEN the crop is applied in the correctly-oriented coordinate system
                    # This handles any rotation direction (90° CW, 90° CCW, etc.) automatically!
                    filter_parts = []
                    if crop_rotated:
                        filter_parts.append("autorotate")
                        print(f"[CROP] Using autorotate before crop (video has rotation metadata)")
                    filter_parts.append(f"crop={cw}:{ch}:{cx}:{cy}")
                    crop_filter = ",".join(filter_parts)
                    
                    crop_cmd = (
                        f'ffmpeg -y -i "{video_path}" '
                        f'-vf "{crop_filter}" '
                        f'-c:v libx264 -preset fast -crf 20 -c:a aac -b:a 128k '
                        f'"{cropped_path}"'
                    )
                    if self._run_ffmpeg(crop_cmd, "Cropping video"):
                        input_video = cropped_path
                        crop_applied = True
                        print(f"[CROP] Applied: x={cx} y={cy} w={cw} h={ch} (rotated={crop_rotated})")
            except Exception as e:
                print(f"[CROP ERROR] {e}")
        
        # When crop is applied, force "cover" mode so the cropped area FILLS the video display area
        # (instead of showing it small with black bars in "fit" mode)
        if crop_applied:
            video_fit_mode = "cover"
            print(f"[CROP] Auto-switched to 'cover' mode so cropped video fills the video area")
        
        # === STEP 1: Prepare background (image/video/solid) ===
        bg_video_path = os.path.join(self.output_dir, f"t_bg_{uid}.mp4")
        temp_files.append(bg_video_path)
        
        if bg_path and os.path.exists(bg_path):
            # User uploaded a background - prepare it
            bg_ext = os.path.splitext(bg_path)[1].lower()
            is_image = bg_ext in {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
            
            if is_image:
                # Image: create video from image at correct duration
                cmd = (
                    f'ffmpeg -y -loop 1 -i "{bg_path}" '
                    f'-vf "scale={W}:{H}:force_original_aspect_ratio=decrease,'
                    f'pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black" '
                    f'-c:v libx264 -preset fast -crf 23 -pix_fmt yuv420p '
                    f'-t {duration} '
                    f'"{bg_video_path}"'
                )
                if not self._run_ffmpeg(cmd, "Creating background from image"):
                    self._cleanup(temp_files)
                    return None
            else:
                # Video: loop with stream_loop, scale to canvas, no audio
                cmd = (
                    f'ffmpeg -y -stream_loop -1 -i "{bg_path}" '
                    f'-vf "scale={W}:{H}:force_original_aspect_ratio=decrease,'
                    f'pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black" '
                    f'-c:v libx264 -preset fast -crf 23 -pix_fmt yuv420p '
                    f'-an -t {duration} '
                    f'"{bg_video_path}"'
                )
                if not self._run_ffmpeg(cmd, "Creating background from video (looped)"):
                    self._cleanup(temp_files)
                    return None
            print(f"[BG] Using custom background: {bg_path}")
        else:
            # No background: use solid black
            cmd = f'ffmpeg -y -f lavfi -i color=c=black:s={W}x{H}:d={duration} -c:v libx264 -preset ultrafast -crf 23 -pix_fmt yuv420p "{bg_video_path}"'
            if not self._run_ffmpeg(cmd, "Creating black background"):
                self._cleanup(temp_files)
                return None
        
        # === STEP 2: Scale video to fit video area ===
        # When crop is applied, make the video display area LARGER so the cropped content is shown more prominently
        vid_w = W - (B * 2)
        vid_h = template.video_height
        if crop_applied:
            # Increase video height significantly — use 80% of the space between video_y and handle_y
            max_available = template.handle_y - template.video_y - 60
            vid_h = min(int(W * 0.75), int(max_available))
            print(f"[CROP] Video area enlarged to {vid_w}×{vid_h} (was {W - (B * 2)}×{template.video_height})")
        
        scaled_path = os.path.join(self.output_dir, f"t_vid_{uid}.mp4")
        temp_files.append(scaled_path)
        
        # Choose scale mode:
        # "fit"   = preserve aspect, shrink to fit, pad with black (like CSS contain)
        # "cover" = preserve aspect, zoom to fill, crop excess (like CSS cover) - BEST for portrait videos!
        # "fill"  = stretch to exact size (DISTORTS aspect ratio - not recommended)
        if video_fit_mode == "cover":
            # Zooms in to fill the area completely, cropping overflowing edges
            # For portrait 1080×1920 in a 1064×1200 area:
            #   scale=1064:1200:force_original_aspect_ratio=increase → makes it 1064×1891
            #   crop=1064:1200 → trims overflowing top/bottom, keeping center
            scale_filter = (
                f"scale={vid_w}:{vid_h}:force_original_aspect_ratio=increase,"
                f"crop={vid_w}:{vid_h}"
            )
            scale_desc = "Cover (zoom to fill)"
        elif video_fit_mode == "fill":
            scale_filter = f"scale={vid_w}:{vid_h}"
            scale_desc = "Stretch to fill"
        else:
            scale_filter = f"scale={vid_w}:{vid_h}:force_original_aspect_ratio=decrease,pad={vid_w}:{vid_h}:(ow-iw)/2:(oh-ih)/2:black"
            scale_desc = "Fit with padding"
        
        cmd = (
            f'ffmpeg -y -i "{input_video}" '
            f'-vf "{scale_filter}" '
            f'-c:v libx264 -preset fast -crf 20 -c:a aac -b:a 128k '
            f'"{scaled_path}"'
        )
        if not self._run_ffmpeg(cmd, f"Scaling video ({scale_desc})"):
            self._cleanup(temp_files)
            return None
        
        # === STEP 3: Generate all overlay images using Pillow ===
        overlay_dir = self.output_dir
        
        # 3a: Create text overlay image
        # Always use the story text above the video (regular create mode layout)
        display_text = story_text
        text_img_path, overflow_lines = self._create_text_overlay(display_text, template, overlay_dir, uid)
        if not text_img_path:
            self._cleanup(temp_files)
            return None
        temp_files.append(text_img_path)
        
        print(f"[TEXT] Story text: '{display_text[:60]}...' ({overflow_lines} overflow lines)")
        
        # 3b: Create header overlay (logo + channel name + handle)
        header_img_path = self._create_header_overlay(
            channel_name, channel_handle, logo_path, template, overlay_dir, uid
        )
        if header_img_path:
            temp_files.append(header_img_path)
        
        # 3c: Create bottom handle overlay (shifted down if there's overflow text)
        handle_img_path = self._create_handle_overlay(
            channel_handle, template, overlay_dir, uid,
            overflow_lines=overflow_lines
        )
        if handle_img_path:
            temp_files.append(handle_img_path)
        
        # 3d: Create niche label overlay (shifted down if there's overflow text)
        # When crop is applied, skip the niche label to free up more vertical space for the larger video
        niche_img_path = None
        if niche_text and niche_text.strip() and not crop_applied:
            niche_img_path = self._create_niche_overlay(
                niche_text.strip(), template, overlay_dir, uid,
                overflow_lines=overflow_lines
            )
            if niche_img_path:
                temp_files.append(niche_img_path)
        
        if crop_applied and niche_text and niche_text.strip():
            print(f"[CROP] Skipping niche label '{niche_text}' to give more room for the enlarged video")
        
        # === STEP 4: Combine all overlay images into one composite ===
        # This avoids multiple FFmpeg re-encode passes
        composite_path = os.path.join(self.output_dir, f"t_composite_{uid}.png")
        temp_files.append(composite_path)
        
        try:
            # Create full-size RGBA composite
            composite = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            
            # Add borders using draw (not FFmpeg)
            if B > 0:
                border_color = template.border_color.lstrip("#")
                br, bg, bb = tuple(int(border_color[i:i+2], 16) for i in (0, 2, 4))
                # Left border
                composite.paste(Image.new("RGBA", (B, H), (br, bg, bb, 255)), (0, 0))
                # Right border
                composite.paste(Image.new("RGBA", (B, H), (br, bg, bb, 255)), (W - B, 0))
            
            # Paste text overlay
            if text_img_path:
                text_img = Image.open(text_img_path).convert("RGBA")
                composite = Image.alpha_composite(composite, text_img)
            
            # Paste header
            if header_img_path:
                header_img = Image.open(header_img_path).convert("RGBA")
                composite = Image.alpha_composite(composite, header_img)
            
            # Paste handle
            if handle_img_path:
                handle_img = Image.open(handle_img_path).convert("RGBA")
                composite = Image.alpha_composite(composite, handle_img)
            
            # Paste niche label
            if niche_img_path:
                niche_img = Image.open(niche_img_path).convert("RGBA")
                composite = Image.alpha_composite(composite, niche_img)
            
            composite.save(composite_path)
            print(f"[PILLOW] Composite overlay created")
        except Exception as e:
            print(f"[PILLOW ERROR] Composite: {e}")
            self._cleanup(temp_files)
            return None
        
        # === STEP 5: Single FFmpeg command ===
        # Overlay video on bg, overlay composite, then apply copyright-free effects
        # Effects: slight crop shift (avoids Content ID), optional audio pitch shift
        filter_str = (
            f"[0:v][1:v]overlay={B}:{template.video_y}[vid];"
            f"[vid][2:v]overlay=0:0:format=auto[over];"
            f"[over]crop=iw-4:ih-4:2:2,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black"
        )
        
        # Audio pitch shift: asetrate changes pitch, aresample+atempo restore speed
        audio_filter = ""
        if audio_pitch_shift:
            ratio = 1.07  # 7% pitch shift - enough for copyright, subtle enough for listening
            atempo_val = 1.0 / ratio
            audio_filter = f'-af "asetrate=48000*{ratio},aresample=48000,atempo={atempo_val:.6f}" '
            print("[AUDIO] Pitch shift enabled (+7%)")
        
        cmd = (
            f'ffmpeg -y '
            f'-i "{bg_video_path}" -i "{scaled_path}" -i "{composite_path}" '
            f'-filter_complex "{filter_str}" '
            f'-map 1:a? '
            f'{audio_filter}'
            f'-r 30 -pix_fmt yuv420p '
            f'-c:v libx264 -preset fast -crf 20 -c:a aac -shortest '
            f'"{output_path}"'
        )
        
        if not self._run_ffmpeg(cmd, "Composing final video"):
            self._cleanup(temp_files)
            return None        # === STEP 6: Burn subtitles if requested === 
        if add_subtitles:
            try:
                from services.subtitle import generate_srt, generate_srt_simple
                
                # Priority 1: Voice recognition via faster-whisper
                # Uses the original video audio to generate accurate, time-aligned subtitles
                print("[SUBTITLES] Transcribing audio with Whisper AI (voice recognition)...")
                srt_path = generate_srt(video_path, self.output_dir)
                
                # Fallback: Text-based subtitle generation (no audio needed)
                if srt_path is None:
                    print("[SUBTITLES] Whisper failed, falling back to text-based subtitles")
                    srt_path = generate_srt_simple(video_path, story_text, self.output_dir)
                
                if srt_path and os.path.exists(srt_path):
                    subbed_path = os.path.join(self.output_dir, f"t_subbed_{uid}.mp4")
                    temp_files.append(subbed_path)
                    
                    # FFmpeg subtitles filter requires forward slashes on ALL platforms
                    srt_fwd = srt_path.replace("\\", "/")
                    # Smaller subtitle font with clean style
                    # Note: don't quote force_style value - FFmpeg parses by colon
                    sub_cmd = (
                        f'ffmpeg -y -i "{output_path}" '
                        f'-vf "subtitles={srt_fwd}:force_style=FontSize=20:PrimaryColour=&H00FFFFFF:OutlineColour=&H00000000:BorderStyle=1:Outline=1:Shadow=0:BackColour=&H80000000:Italic=0:Alignment=2:WrapStyle=1" '
                        f'-c:v libx264 -preset fast -crf 20 '
                        f'-c:a aac -b:a 128k '
                        f'"{subbed_path}"'
                    )
                    if self._run_ffmpeg(sub_cmd, "Burning subtitles"):
                        os.replace(subbed_path, output_path)
                        print("[SUBTITLES] Burned into video")
            except Exception as e:
                print(f"[SUBTITLES ERROR] {e}")
        
        self._cleanup(temp_files)
        return output_path
    
    def _create_text_overlay(self, story_text: str, template: LayoutConfig,
                              output_dir: str, uid: str) -> tuple:
        """
        Create a transparent PNG with colored text using Pillow.
        
        Returns: (path to overlay image, overflow_line_count) or (None, 0) on failure.
        
        Text layout:
        - Lines that fit ABOVE the video are rendered at the normal text_y position.
        - Any OVERFLOW lines are rendered BELOW the video (between video bottom and handle).
        - The 6-line cap has been REMOVED — all text is shown!
        """
        try:
            W, H = template.width, template.height
            fontsize = template.text_fontsize
            font = self._get_font(fontsize)
            
            # Create transparent image
            img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Word wrap
            words = story_text.split()
            max_width = template.text_width
            lines = []
            current_line = []
            for word in words:
                test_line = " ".join(current_line + [word])
                bbox = draw.textbbox((0, 0), test_line, font=font)
                if bbox[2] - bbox[0] <= max_width:
                    current_line.append(word)
                else:
                    lines.append(current_line)
                    current_line = [word]
            if current_line:
                lines.append(current_line)
            
            # ─── NO CAP — all lines are rendered! ───
            
            # Assign colors and draw
            color_map = {
                "white": template.text_color_white,
                "red": template.text_color_red,
                "blue": template.text_color_blue,
                "yellow": template.text_color_yellow,
            }
            
            text_start_x = template.border_width + 65
            line_height = fontsize + 12
            
            # 🚀 Text is ABOVE the video
            # Available vertical space above video
            space_above = template.video_y - template.text_y - 20  # 20px padding
            max_lines_above = max(1, space_above // line_height)
            
            above_lines = lines[:max_lines_above]
            overflow_lines = lines[max_lines_above:]
            
            # ── Draw lines ABOVE the video ──
            for line_idx, line_words in enumerate(above_lines):
                colored = assign_text_colors(line_words)
                curr_x = text_start_x
                curr_y = template.text_y + (line_idx * line_height)
                
                for word, color_name in colored:
                    hex_color = color_map.get(color_name, template.text_color_white)
                    rgb = tuple(int(hex_color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
                    
                    # Draw shadow
                    draw.text((curr_x + 3, curr_y + 3), word, font=font,
                              fill=(0, 0, 0, 153))
                    # Draw text
                    draw.text((curr_x, curr_y), word, font=font, fill=(*rgb, 255))
                    
                    # Move position
                    bbox = draw.textbbox((0, 0), word, font=font)
                    curr_x += (bbox[2] - bbox[0]) + 18
            
            # ── Draw OVERFLOW lines BELOW the video ──
            if overflow_lines:
                video_bottom = template.video_y + template.video_height
                overflow_start_y = video_bottom + 30  # 30px padding below video
                
                # Use slightly smaller font for overflow text to fit more
                overflow_fontsize = max(28, fontsize - 12)
                overflow_font = self._get_font(overflow_fontsize)
                overflow_line_height = overflow_fontsize + 8
                
                print(f"[TEXT OVERFLOW] {len(overflow_lines)} lines placed below video (starting at y={overflow_start_y})")
                
                for line_idx, line_words in enumerate(overflow_lines):
                    colored = assign_text_colors(line_words)
                    curr_x = text_start_x + 10  # slight indent for overflow
                    curr_y = overflow_start_y + (line_idx * overflow_line_height)
                    
                    # Stop if we'd go past the handle area
                    if curr_y + overflow_line_height > template.handle_y - 20:
                        print(f"[TEXT OVERFLOW] Stopped at line {line_idx+1}/{len(overflow_lines)} — ran out of space")
                        break
                    
                    for word, color_name in colored:
                        hex_color = color_map.get(color_name, template.text_color_white)
                        rgb = tuple(int(hex_color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
                        
                        # Draw shadow
                        draw.text((curr_x + 2, curr_y + 2), word, font=overflow_font,
                                  fill=(0, 0, 0, 153))
                        # Draw text
                        draw.text((curr_x, curr_y), word, font=overflow_font, fill=(*rgb, 255))
                        
                        # Move position
                        bbox = draw.textbbox((0, 0), word, font=overflow_font)
                        curr_x += (bbox[2] - bbox[0]) + 10
            
            path = os.path.join(output_dir, f"text_overlay_{uid}.png")
            img.save(path)
            print(f"[PILLOW] Text overlay created: {path} ({len(above_lines)} above + {len(overflow_lines)} below video)")
            return (path, len(overflow_lines))
        except Exception as e:
            print(f"[PILLOW ERROR] Text overlay: {e}")
            return (None, 0)
    
    def _create_header_overlay(self, channel_name: str, channel_handle: str,
                                logo_path: Optional[str], template: LayoutConfig,
                                output_dir: str, uid: str) -> Optional[str]:
        """Create header overlay with logo + channel name + handle"""
        try:
            W, H = template.width, template.height
            img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            header_x = template.border_width + 20
            header_y = template.header_y + 60
            
            # Draw logo if available
            logo_x = header_x
            if logo_path and os.path.exists(logo_path):
                try:
                    logo_img = Image.open(logo_path).convert("RGBA")
                    logo_size = template.logo_size
                    logo_img = logo_img.resize((logo_size, logo_size), Image.LANCZOS)
                    img.paste(logo_img, (header_x, header_y), logo_img)
                    logo_x = header_x + logo_size + 15
                except Exception as e:
                    print(f"[PILLOW] Logo error: {e}")
            
            # Draw channel name
            name_font = self._get_font(template.channel_name_fontsize)
            name_y = header_y + 2
            # Shadow
            draw.text((logo_x + 2, name_y + 2), channel_name, font=name_font,
                      fill=(0, 0, 0, 128))
            draw.text((logo_x, name_y), channel_name, font=name_font,
                      fill=(255, 255, 255, 255))
            
            # Draw handle
            handle_font = self._get_font(template.channel_handle_fontsize)
            handle_y = name_y + template.channel_name_fontsize + 6
            draw.text((logo_x + 1, handle_y + 1), channel_handle, font=handle_font,
                      fill=(0, 0, 0, 80))
            draw.text((logo_x, handle_y), channel_handle, font=handle_font,
                      fill=(136, 136, 136, 255))
            
            path = os.path.join(output_dir, f"header_{uid}.png")
            img.save(path)
            return path
        except Exception as e:
            print(f"[PILLOW ERROR] Header: {e}")
            return None
    
    def _create_handle_overlay(self, channel_handle: str, template: LayoutConfig,
                                output_dir: str, uid: str,
                                overflow_lines: int = 0) -> Optional[str]:
        """Create bottom channel handle watermark"""
        try:
            font = self._get_font(template.handle_fontsize)
            bbox = font.getbbox(channel_handle)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            
            # Create just the right-sized image
            img = Image.new("RGBA", (tw + 20, th + 10), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Shadow
            draw.text((12, 7), channel_handle, font=font, fill=(0, 0, 0, 128))
            draw.text((10, 5), channel_handle, font=font,
                      fill=(255, 255, 255, 179))  # white@0.7
            
            # Place on full canvas (shifted down if overflow text is below video)
            full = Image.new("RGBA", (template.width, template.height), (0, 0, 0, 0))
            x = (template.width - tw - 20) // 2
            
            # Shift handle down if there's overflow text
            handle_y = template.handle_y
            if overflow_lines > 0:
                overflow_fontsize = max(28, template.text_fontsize - 12)
                overflow_line_height = overflow_fontsize + 8
                handle_y += overflow_lines * overflow_line_height + 40
            
            y = handle_y
            full.paste(img, (x, y), img)
            
            path = os.path.join(output_dir, f"handle_{uid}.png")
            full.save(path)
            return path
        except Exception as e:
            print(f"[PILLOW ERROR] Handle: {e}")
            return None
    
    def _create_niche_overlay(self, niche_text: str, template: LayoutConfig,
                               output_dir: str, uid: str,
                               overflow_lines: int = 0) -> Optional[str]:
        """Create a niche category label displayed between the video and channel handle.
        
        Positioned centered between video bottom (y≈1440) and handle (y≈1700),
        with a dark pill background for readability.
        
        If there's overflow text below the video, the niche is shifted down
        to sit below the extra text.
        """
        try:
            font = self._get_font(48)
            bbox = font.getbbox(niche_text)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            
            # Pill background dimensions
            padding_x = 30
            padding_y = 12
            corner_r = 24
            pill_w = tw + padding_x * 2
            pill_h = th + padding_y * 2
            
            # Create the niche image with a dark pill background
            img = Image.new("RGBA", (pill_w, pill_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Use Pillow's built-in rounded_rectangle (fast C-level rendering)
            draw.rounded_rectangle(
                [(0, 0), (pill_w - 1, pill_h - 1)],
                radius=corner_r,
                fill=(0, 0, 0, 200)  # semi-transparent black pill
            )
            
            # Add subtle border glow to the pill
            draw.rounded_rectangle(
                [(0, 0), (pill_w - 1, pill_h - 1)],
                radius=corner_r,
                outline=(255, 255, 255, 30),
                width=1
            )
            
            # Determine text color based on niche keywords
            niche_lower = niche_text.lower()
            if "crime" in niche_lower or "mystery" in niche_lower:
                text_color = (255, 70, 70, 255)  # red for crime
            elif "movie" in niche_lower or "film" in niche_lower or "hollywood" in niche_lower:
                text_color = (255, 210, 50, 255)  # gold for movies
            elif "sport" in niche_lower:
                text_color = (50, 200, 255, 255)  # blue for sports
            elif "story" in niche_lower or "reddit" in niche_lower:
                text_color = (255, 150, 50, 255)  # orange for stories
            elif "fact" in niche_lower:
                text_color = (162, 155, 254, 255)  # purple for facts
            else:
                text_color = (255, 255, 255, 255)  # white default
            
            # Draw text with shadow
            text_x = padding_x
            text_y = padding_y
            draw.text((text_x + 2, text_y + 2), niche_text, font=font,
                      fill=(0, 0, 0, 180))
            draw.text((text_x, text_y), niche_text, font=font, fill=text_color)
            
            # Place on full canvas - centered below video, above handle
            full = Image.new("RGBA", (template.width, template.height), (0, 0, 0, 0))
            video_bottom = template.video_y + template.video_height
            
            # If there's overflow text below the video, shift the niche down
            overflow_offset = 0
            if overflow_lines > 0:
                overflow_fontsize = max(28, template.text_fontsize - 12)
                overflow_line_height = overflow_fontsize + 8
                overflow_offset = overflow_lines * overflow_line_height + 40  # 40px padding
            
            # Position centered between video bottom (or overflow text end) and handle
            lower_bound = template.handle_y
            upper_bound = video_bottom + overflow_offset
            space_available = lower_bound - upper_bound
            
            niche_y = upper_bound + max(10, (space_available - pill_h) // 2)
            niche_x = (template.width - pill_w) // 2
            full.paste(img, (niche_x, niche_y), img)
            
            path = os.path.join(output_dir, f"niche_{uid}.png")
            full.save(path)
            print(f"[PILLOW] Niche overlay created: '{niche_text}' at y={niche_y}")
            return path
        except Exception as e:
            print(f"[PILLOW ERROR] Niche: {e}")
            return None


def generate_short(
    video_path: str,
    story_text: str,
    hook_text: str = None,
    channel_name: str = "YourChannel",
    channel_handle: str = "@yourchannel",
    logo_path: str = None,
    bg_path: str = None,
    template_name: str = "evergreen",
    output_path: str = None,
    add_subtitles: bool = False,
    crop: Optional[dict] = None,
    crop_rotated: bool = False,
    video_fit_mode: str = "fit",
    audio_pitch_shift: bool = False,
    niche_text: Optional[str] = None,
) -> Optional[str]:
    """Generate a viral Short.
    
    Creates a viral Short with story text above the video, channel branding,
    and optional background/logo/subtitles.
    
    Args:
        hook_text: The AI-generated viral hook text
        template_name: Display name of the template
    """
    from services.template import get_template
    
    template = get_template(template_name)
    if template is None:
        from services.template import TEMPLATES
        template = list(TEMPLATES.values())[0]
    
    editor = VideoEditor()
    display_text = story_text[:500]
    
    return editor.compose_evergreen_short(
        video_path=video_path,
        story_text=display_text,
        channel_name=channel_name,
        channel_handle=channel_handle,
        logo_path=logo_path,
        bg_path=bg_path,
        template=template,
        output_path=output_path,
        add_subtitles=add_subtitles,
        crop=crop,
        crop_rotated=crop_rotated,
        video_fit_mode=video_fit_mode,
        audio_pitch_shift=audio_pitch_shift,
        niche_text=niche_text,
        hook_text=hook_text
    )
