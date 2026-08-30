import subprocess
import os
import imageio_ffmpeg

ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
src_video = r"c:/Users/user/Alpha-Pro-Mena-CRM\wall.mp4"
out_dir = r"c:/Users/user/Alpha-Pro-Mena-CRM\frontend\public\videos"
os.makedirs(out_dir, exist_ok=True)

out_mp4 = os.path.join(out_dir, "wall.mp4")
out_webm = os.path.join(out_dir, "wall.webm")

print("1. Transcoding optimized 1080p MP4 (H.264, faststart, target < 3MB)...")
cmd_mp4 = [
    ffmpeg_exe, "-y",
    "-i", src_video,
    "-vf", "scale=1920:1080",
    "-c:v", "libx264",
    "-preset", "slow",
    "-crf", "22",
    "-pix_fmt", "yuv420p",
    "-movflags", "+faststart",
    "-an",
    out_mp4
]
p1 = subprocess.run(cmd_mp4, capture_output=True, text=True)
if p1.returncode != 0:
    print("MP4 Error:", p1.stderr)
else:
    size_mp4 = os.path.getsize(out_mp4)
    print(f"MP4 created: {out_mp4} ({size_mp4 / (1024*1024):.2f} MB)")

print("\n2. Transcoding optimized 1080p WebM (VP9, target < 2.5MB)...")
cmd_webm = [
    ffmpeg_exe, "-y",
    "-i", src_video,
    "-vf", "scale=1920:1080",
    "-c:v", "libvpx-vp9",
    "-b:v", "0",
    "-crf", "30",
    "-pix_fmt", "yuv420p",
    "-an",
    out_webm
]
p2 = subprocess.run(cmd_webm, capture_output=True, text=True)
if p2.returncode != 0:
    print("WebM Error:", p2.stderr)
else:
    size_webm = os.path.getsize(out_webm)
    print(f"WebM created: {out_webm} ({size_webm / (1024*1024):.2f} MB)")

print("\n[OK] Video optimization complete!")
