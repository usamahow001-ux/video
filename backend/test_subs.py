"""Test subtitles burning with FFmpeg"""
import os, subprocess

ffmpeg_bin = os.path.join(os.getcwd(), "ffmpeg_bin")
os.environ["PATH"] = ffmpeg_bin + os.pathsep + os.environ.get("PATH", "")
out = "output"

# Create a simple SRT
srt_path = os.path.join(out, "test_debug.srt")
with open(srt_path, "w") as f:
    f.write("""1
00:00:01,000 --> 00:00:08,000
Hello this is a test subtitle line one

2
00:00:09,000 --> 00:00:15,000
This is the second subtitle line
""")

print(f"SRT created: {srt_path}")
print(f"SRT exists: {os.path.exists(srt_path)}")

# Create a test video
base = os.path.join(out, "test_base.mp4")
r = subprocess.run(
    f'ffmpeg -y -f lavfi -i color=c=black:s=320x240:d=20 -c:v libx264 -preset ultrafast -crf 23 "{base}"',
    shell=True, capture_output=True, text=True, timeout=30
)
print(f"Base video: rc={r.returncode}")
if r.returncode != 0:
    print(f"Error: {r.stderr[:200]}")

# Forward slashes - simplest syntax
print("\n=== Test: forward slashes ===")
out1 = os.path.join(out, "test_sub_a.mp4")
srt_fwd = srt_path.replace("\\", "/")
cmd = f'ffmpeg -y -i "{base}" -vf "subtitles={srt_fwd}" -c:v libx264 -preset fast -crf 23 "{out1}"'
print(f"CMD: {cmd}")
r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
print(f"rc={r.returncode}")
if r.returncode != 0:
    print(f"Stderr: {r.stderr[:400]}")
else:
    print("OK!")

# With original path (has backslashes)
print("\n=== Test: original path with backslashes ===")
out2 = os.path.join(out, "test_sub_b.mp4")
cmd = f'ffmpeg -y -i "{base}" -vf "subtitles={srt_path}" -c:v libx264 -preset fast -crf 23 "{out2}"'
print(f"CMD: {cmd}")
r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
print(f"rc={r.returncode}")
if r.returncode != 0:
    print(f"Stderr: {r.stderr[:400]}")
else:
    print("OK!")

# Check if subtitles filter is available
print("\n=== Filter check ===")
r = subprocess.run("ffmpeg -filters 2>&1 | findstr subtitle", shell=True, capture_output=True, text=True, timeout=10)
print(f"Available subtitle filters: {r.stdout[:300]}")

print("\nDone")
