"""
Subtitle Service - Generates SRT subtitles from video audio
Uses faster-whisper (runs locally, completely free)
"""

import os
import json
from pathlib import Path


def format_time(seconds: float) -> str:
    """Convert seconds to SRT timestamp format: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_srt(video_path: str, output_dir: str = None) -> str:
    """
    Generate SRT subtitle file from video audio using faster-whisper.
    
    Args:
        video_path: Path to the video file
        output_dir: Directory to save the SRT file (default: same as video)
    
    Returns:
        Path to the generated SRT file, or None if failed
    """
    if output_dir is None:
        output_dir = os.path.dirname(video_path)
    
    srt_path = os.path.join(output_dir, "subtitles.srt")
    
    try:
        from faster_whisper import WhisperModel
        
        # Use CPU (no GPU needed)
        model = WhisperModel("base", device="cpu", compute_type="int8")
        
        segments, info = model.transcribe(
            video_path,
            beam_size=5,
            language="en",
            vad_filter=True,  # Filter out silence
        )
        
        count = 0
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments, start=1):
                start_time = format_time(segment.start)
                end_time = format_time(segment.end)
                text = segment.text.strip()
                
                if text:
                    f.write(f"{i}\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{text}\n\n")
                    count += 1
        
        if count == 0:
            print(f"[SUBTITLES] No speech detected in video")
            # Clean up empty file
            if os.path.exists(srt_path):
                try: os.remove(srt_path)
                except: pass
            return None
        
        print(f"[SUBTITLES] Voice recognition: {count} subtitle segments generated")
        return srt_path
        
    except ImportError:
        print("[WARN] faster-whisper not installed. Skipping subtitles.")
        print("   Install: pip install faster-whisper")
        return None
    except Exception as e:
        print(f"[SUBTITLE ERROR] {e}")
        return None


def generate_srt_simple(video_path: str, text: str, output_dir: str = None) -> str:
    """
    Generate a simple SRT file from the story text (no audio transcription needed).
    Creates timed subtitles that match the video duration.
    
    Args:
        video_path: Path to the video for duration reference
        text: The story text to use as subtitles
        output_dir: Directory to save the SRT file
    
    Returns:
        Path to the generated SRT file
    """
    if output_dir is None:
        output_dir = os.path.dirname(video_path)
    
    srt_path = os.path.join(output_dir, "subtitles.srt")
    
    try:
        try:
            from moviepy.editor import VideoFileClip  # moviepy 1.x
        except ImportError:
            from moviepy import VideoFileClip  # moviepy 2.x
        
        # Get video duration
        with VideoFileClip(video_path) as clip:
            duration = clip.duration
    except:
        # Default duration if we can't read the video
        duration = 30
    
    # Split text into subtitle chunks
    words = text.split()
    chunks = []
    chunk_size = max(3, len(words) // max(1, int(duration // 3)))
    
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
    
    num_chunks = len(chunks)
    chunk_duration = duration / max(1, num_chunks)
    
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, chunk in enumerate(chunks):
            start = i * chunk_duration
            end = min((i + 1) * chunk_duration, duration)
            
            f.write(f"{i + 1}\n")
            f.write(f"{format_time(start)} --> {format_time(end)}\n")
            f.write(f"{chunk}\n\n")
    
    print(f"[SUBTITLES] Simple subtitles generated: {srt_path}")
    return srt_path
