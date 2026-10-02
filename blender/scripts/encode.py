"""Encode a rendered PNG sequence into the stock delivery files.

    python encode.py renders renders

Produces:
  <slug>-4k.mp4            H.264 / yuv420p, the review master
  <slug>-4k-prores.mov     ProRes 422 HQ, the archival master
  <slug>-contact-sheet.jpg 2x2 market sheet
  <slug>-poster.png        frame 0
  render-report.json       measured delivery spec

Only the range actually on disk is encoded, so the same script produces a
draft master and a full one without a dry-run flag.
"""

import json
import os
import re
import shutil
import subprocess
import sys

FPS = int(os.environ.get("FPS", "60"))
EXPECTED_FRAMES = int(os.environ.get("EXPECTED_FRAMES", "720"))
SLUG = os.environ.get("SLUG", "003_pcb-ai-chip-loop")
FRAME_PREFIX = os.environ.get("FRAME_PREFIX", "pcb_")

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


def have(tool):
    return subprocess.run(["where", tool], capture_output=True,
                          shell=True).returncode == 0


def discover(src):
    pat = re.compile(r"^%s(\d+)\.png$" % re.escape(FRAME_PREFIX))
    out = []
    for name in os.listdir(src):
        m = pat.match(name)
        if m:
            out.append(int(m.group(1)))
    return sorted(out)


def run(cmd):
    print("[encode] %s" % " ".join(cmd[:4]), "...", flush=True)
    subprocess.run(cmd, check=True)


def main():
    if FFMPEG is None or FFPROBE is None:
        sys.exit("[encode] ffmpeg/ffprobe not found on PATH")

    src = sys.argv[1] if len(sys.argv) > 1 else "renders"

    numbers = discover(src)
    if not numbers:
        sys.exit("[encode] no %s####.png frames in %s" % (FRAME_PREFIX, src))

    first, last = numbers[0], numbers[-1]
    count = len(numbers)
    if numbers != list(range(first, last + 1)):
        sys.exit("[encode] frame numbering has gaps; refusing to encode")

    print("[encode] %d frames, %d..%d, %.3f s"
          % (count, first, last, count / FPS))
    if count != EXPECTED_FRAMES:
        print("[encode] NOTE: encoding %d of the expected %d frames"
              % (count, EXPECTED_FRAMES))

    mp4 = os.path.join(src, "%s-4k.mp4" % SLUG)
    mov = os.path.join(src, "%s-4k-prores.mov" % SLUG)
    sheet = os.path.join(src, "%s-contact-sheet.jpg" % SLUG)
    poster = os.path.join(src, "%s-poster.png" % SLUG)

    # H.264 review master. CRF 16 keeps the emissive traces clean and stays
    # well inside Adobe's 3.9 GB ceiling for a 12 s clip.
    run([
        FFMPEG, "-y", "-framerate", str(FPS),
        "-start_number", str(first),
        "-i", os.path.join(src, "%s%%04d.png" % FRAME_PREFIX),
        "-frames:v", str(count),
        "-c:v", "libx264", "-preset", "slow", "-crf", "16",
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "5.2",
        "-movflags", "+faststart",
        mp4,
    ])

    # ProRes 422 HQ archival master.
    run([
        FFMPEG, "-y", "-framerate", str(FPS),
        "-start_number", str(first),
        "-i", os.path.join(src, "%s%%04d.png" % FRAME_PREFIX),
        "-frames:v", str(count),
        "-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le",
        mov,
    ])

    # Market sheet: four frames spread across the clip.
    picks = sorted({0, count // 3, (2 * count) // 3, count - 1})
    expr = "+".join("eq(n\\,%d)" % p for p in picks)
    run([
        FFMPEG, "-y", "-framerate", str(FPS),
        "-start_number", str(first),
        "-i", os.path.join(src, "%s%%04d.png" % FRAME_PREFIX),
        "-frames:v", str(count),
        "-vf", "select='%s',scale=1280:-2,tile=2x2" % expr,
        "-frames:v", "1", "-q:v", "3",
        sheet,
    ])

    run([
        FFMPEG, "-y", "-i", os.path.join(src, "%s%04d.png" % (FRAME_PREFIX, first)),
        "-frames:v", "1",
        poster,
    ])

    probe = json.loads(subprocess.run([
        FFPROBE, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,nb_frames,pix_fmt",
        "-show_entries", "format=duration,size",
        "-of", "json", mp4,
    ], capture_output=True, text=True, check=True).stdout)

    report = {
        "slug": SLUG,
        "frames_encoded": count,
        "frame_range": [first, last],
        "expected_frames": EXPECTED_FRAMES,
        "encoded_duration_s": round(count / FPS, 3),
        "h264": probe,
        "prores_bytes": os.path.getsize(mov),
    }
    with open(os.path.join(src, "render-report.json"), "w") as fh:
        json.dump(report, fh, indent=2)

    stream = probe["streams"][0]
    print("[encode] %dx%d %s %s frames %ss"
          % (stream["width"], stream["height"], stream["r_frame_rate"],
             stream.get("nb_frames"), probe["format"]["duration"]))
    for path in (mp4, mov, sheet, poster):
        print("[encode] %-44s %8.1f MB"
              % (os.path.basename(path), os.path.getsize(path) / (1024 * 1024)))

    if os.path.getsize(mp4) / (1024 ** 3) > 3.9:
        print("[encode] WARNING: H.264 exceeds the 3.9 GB marketplace limit")


if __name__ == "__main__":
    main()