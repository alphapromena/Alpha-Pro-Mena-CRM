import subprocess
import os
import imageio_ffmpeg

ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
src_video2 = r"F:\New folder\12526998_3840_2160_24fps.mp4"
out_dir = r"F:\New folder\frontend\public\videos"
os.makedirs(out_dir, exist_ok=True)

out_mp4_2 = os.path.join(out_dir, "wall2.mp4")
out_webm_2 = os.path.join(out_dir, "wall2.webm")

print("1. Transcoding optimized second video (1080p MP4 with enhanced brightness/contrast)...")
cmd_mp4_2 = [
    ffmpeg_exe, "-y",
    "-i", src_video2,
    "-vf", "scale=1920:1080,eq=brightness=0.06:contrast=1.1:saturation=1.15",
    "-c:v", "libx264",
    "-preset", "slow",
    "-crf", "22",
    "-pix_fmt", "yuv420p",
    "-movflags", "+faststart",
    "-an",
    out_mp4_2
]
p1 = subprocess.run(cmd_mp4_2, capture_output=True, text=True)
if p1.returncode != 0:
    print("MP4 Error:", p1.stderr)
else:
    size_mp4 = os.path.getsize(out_mp4_2)
    print(f"MP4 created: {out_mp4_2} ({size_mp4 / (1024*1024):.2f} MB)")

print("\n2. Transcoding optimized second video (1080p WebM with enhanced brightness/contrast)...")
cmd_webm_2 = [
    ffmpeg_exe, "-y",
    "-i", src_video2,
    "-vf", "scale=1920:1080,eq=brightness=0.06:contrast=1.1:saturation=1.15",
    "-c:v", "libvpx-vp9",
    "-b:v", "0",
    "-crf", "30",
    "-pix_fmt", "yuv420p",
    "-an",
    out_webm_2
]
p2 = subprocess.run(cmd_webm_2, capture_output=True, text=True)
if p2.returncode != 0:
    print("WebM Error:", p2.stderr)
else:
    size_webm = os.path.getsize(out_webm_2)
    print(f"WebM created: {out_webm_2} ({size_webm / (1024*1024):.2f} MB)")

# Also re-encode wall.mp4 with brightness boost if beneficial
src_video1 = r"F:\New folder\wall.mp4"
out_mp4_1 = os.path.join(out_dir, "wall.mp4")
out_webm_1 = os.path.join(out_dir, "wall.webm")

print("\n3. Re-encoding first video (wall.mp4) with enhanced brightness boost...")
cmd_mp4_1 = [
    ffmpeg_exe, "-y",
    "-i", src_video1,
    "-vf", "scale=1920:1080,eq=brightness=0.06:contrast=1.1:saturation=1.15",
    "-c:v", "libx264",
    "-preset", "slow",
    "-crf", "22",
    "-pix_fmt", "yuv420p",
    "-movflags", "+faststart",
    "-an",
    out_mp4_1
]
subprocess.run(cmd_mp4_1, capture_output=True, text=True)

print("\n4. Re-encoding first video (wall.webm) with enhanced brightness boost...")
cmd_webm_1 = [
    ffmpeg_exe, "-y",
    "-i", src_video1,
    "-vf", "scale=1920:1080,eq=brightness=0.06:contrast=1.1:saturation=1.15",
    "-c:v", "libvpx-vp9",
    "-b:v", "0",
    "-crf", "30",
    "-pix_fmt", "yuv420p",
    "-an",
    out_webm_1
]
subprocess.run(cmd_webm_1, capture_output=True, text=True)

print("\n[OK] Both videos transcoded with high brightness and optimized size!")
