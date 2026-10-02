"""Concatenate lossless FFV1 chunks, QC the loop, and encode the masters.

    python encode.py renders

Input : `renders/seg_NNNN.mkv`, one per matrix chunk, each holding its own
        contiguous frame range and written with every frame a keyframe.

Steps :
  1. Concatenate the segments with a stream copy. No re-encode, so this is
     fast and cannot degrade the pixels.
  2. QC the wrap-around by extracting the first and last frame and comparing
     their PSNR against an ordinary frame step.
  3. Encode the H.264 review master and the ProRes 422 HQ archival master,
     plus a market sheet and a poster.

Because the concatenation is a stream copy, the QC is measuring exactly the
frames the viewer will see.
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
# Low sanity floor plus a relative tolerance, see the seam section below.
SEAM_FLOOR_DB = float(os.environ.get("SEAM_FLOOR_DB", "18"))
SEAM_TOLERANCE_DB = float(os.environ.get("SEAM_TOLERANCE_DB", "1.5"))

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
SEG_RE = re.compile(r"^seg_(\d+)_.*\.mkv$")


def run(cmd, quiet=True):
    print("[encode] %s" % " ".join(cmd[1:5]), flush=True)
    subprocess.run(cmd, check=True, capture_output=quiet)


def psnr(a, b):
    proc = subprocess.run(
        [FFMPEG, "-v", "info", "-i", a, "-i", b, "-lavfi", "psnr",
         "-f", "null", "-"],
        capture_output=True, text=True)
    found = re.findall(r"average:([0-9.]+|inf)", proc.stderr)
    if not found:
        return None
    return float("inf") if found[-1] == "inf" else float(found[-1])


def extract(src, frame, dest):
    subprocess.run([
        FFMPEG, "-v", "error", "-y", "-i", src,
        "-vf", "select=eq(n\\,%d)" % frame,
        "-fps_mode", "passthrough", "-frames:v", "1", dest,
    ], check=True, capture_output=True)


def main():
    if FFMPEG is None or FFPROBE is None:
        sys.exit("[encode] ffmpeg/ffprobe not found on PATH")

    src = sys.argv[1] if len(sys.argv) > 1 else "renders"

    segments = sorted(
        (m.group(1), name)
        for name in os.listdir(src)
        for m in [SEG_RE.match(name)] if m
    )
    if not segments:
        sys.exit("[encode] no seg_*.mkv chunks found in %s" % src)
    if [int(i) for i, _ in segments] != list(range(len(segments))):
        sys.exit("[encode] chunk indices are not contiguous from 0")

    print("[encode] %d chunks: %s .. %s"
          % (len(segments), segments[0][0], segments[-1][0]))

    # --- 1. concatenate with a stream copy ---
    listing = os.path.join(src, "concat.txt")
    with open(listing, "w", encoding="utf-8") as fh:
        for _, name in segments:
            fh.write("file '%s'\n" % os.path.join(src, name))

    lossless = os.path.join(src, "%s-lossless.mkv" % SLUG)
    run([
        FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", listing,
        "-c", "copy", lossless,
    ])

    probe = json.loads(subprocess.run([
        FFPROBE, "-v", "error", "-select_streams", "v:0", "-count_frames",
        "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames,pix_fmt",
        "-show_entries", "format=duration,size",
        "-of", "json", lossless,
    ], capture_output=True, text=True, check=True).stdout)
    stream = probe["streams"][0]
    # FFV1 in Matroska reports no container-level frame count, so the count has
    # to come from -count_frames / nb_read_frames.
    total = int(stream.get("nb_read_frames") or stream.get("nb_frames") or 0)
    print("[encode] stitched %dx%d %s, %s frames, %ss, %.1f MB"
          % (stream["width"], stream["height"], stream["r_frame_rate"],
             total, probe["format"]["duration"],
             os.path.getsize(lossless) / (1024 * 1024)))

    qc = {"frames": total, "expected": EXPECTED_FRAMES,
          "width": stream["width"], "height": stream["height"]}

    if total != EXPECTED_FRAMES:
        qc["verdict"] = "FAIL"
        qc["reason"] = "expected %d frames, stitched %d" % (EXPECTED_FRAMES, total)
        with open(os.path.join(src, "loop_qc.json"), "w") as fh:
            json.dump(qc, fh, indent=2)
        sys.exit("[encode] FAIL: %s" % qc["reason"])

    # --- 2. loop seam QC on real pixels ---
    if total >= 3:
        f0 = os.path.join(src, "_f0000.png")
        fp = os.path.join(src, "_f%04d.png" % (total - 2))
        fl = os.path.join(src, "_f%04d.png" % (total - 1))
        extract(lossless, 0, f0)
        extract(lossless, total - 2, fp)
        extract(lossless, total - 1, fl)

        step = psnr(fp, fl)
        seam = psnr(fl, f0)
        for tmp in (f0, fp, fl):
            os.remove(tmp)

        qc.update({
            "ordinary_step_psnr_db": round(step, 2) if step else None,
            "loop_seam_psnr_db": round(seam, 2) if seam else None,
            "psnr_floor_db": SEAM_FLOOR_DB,
            "seam_tolerance_db": SEAM_TOLERANCE_DB,
        })
        print("[encode] ordinary frame step : %.2f dB" % step)
        print("[encode] loop seam           : %.2f dB" % seam)

        # The gate is relative, not absolute. A perfect loop makes the wrap
        # look like any other frame step, so the seam must sit within a small
        # tolerance of the clip's own interior change. An absolute dB floor
        # would reject a good loop merely because it was rendered at fewer
        # samples: at 24 samples this same clip measures 25.5 dB, at 64 it
        # measures higher. A low absolute floor is still kept underneath, to
        # catch a loop that is not closing at all.
        if step is None or seam is None:
            qc["verdict"] = "FAIL"
            qc["reason"] = "could not measure the seam"
            with open(os.path.join(src, "loop_qc.json"), "w") as fh:
                json.dump(qc, fh, indent=2)
            sys.exit("[encode] FAIL: could not measure the seam")

        if seam < SEAM_FLOOR_DB:
            qc["verdict"] = "FAIL"
            qc["reason"] = "seam %.2f dB is below the %.0f dB sanity floor" % (
                seam, SEAM_FLOOR_DB)
            with open(os.path.join(src, "loop_qc.json"), "w") as fh:
                json.dump(qc, fh, indent=2)
            sys.exit("[encode] FAIL: %s" % qc["reason"])

        deficit = step - seam
        if deficit > SEAM_TOLERANCE_DB:
            qc["verdict"] = "FAIL"
            qc["reason"] = ("seam is %.2f dB below an ordinary frame step, "
                            "tolerance is %.1f dB" % (deficit, SEAM_TOLERANCE_DB))
            with open(os.path.join(src, "loop_qc.json"), "w") as fh:
                json.dump(qc, fh, indent=2)
            sys.exit("[encode] FAIL: %s" % qc["reason"])

        qc["verdict"] = "PASS"
        qc["seam_deficit_db"] = round(deficit, 2)
        print("[encode] seam is %.2f dB %s an ordinary step (tolerance %.1f dB)"
              % (abs(deficit),
                 "above" if deficit <= 0 else "below",
                 SEAM_TOLERANCE_DB))

    with open(os.path.join(src, "loop_qc.json"), "w") as fh:
        json.dump(qc, fh, indent=2)

    # --- 3. delivery masters ---
    mp4 = os.path.join(src, "%s-4k.mp4" % SLUG)
    mov = os.path.join(src, "%s-4k-prores.mov" % SLUG)
    sheet = os.path.join(src, "%s-contact-sheet.jpg" % SLUG)
    poster = os.path.join(src, "%s-poster.png" % SLUG)

    run([FFMPEG, "-y", "-i", lossless, "-c:v", "libx264", "-preset", "slow",
         "-crf", "16", "-pix_fmt", "yuv420p", "-profile:v", "high",
         "-level", "5.2", "-movflags", "+faststart", mp4])

    run([FFMPEG, "-y", "-i", lossless, "-c:v", "prores_ks", "-profile:v", "3",
         "-pix_fmt", "yuv422p10le", mov])

    picks = sorted({0, total // 3, (2 * total) // 3, total - 1})
    expr = "+".join("eq(n\\,%d)" % p for p in picks)
    run([FFMPEG, "-y", "-i", lossless, "-vf",
         "select='%s',scale=1280:-2,tile=2x2" % expr,
         "-frames:v", "1", "-q:v", "3", sheet])

    extract(lossless, 0, poster)

    final = json.loads(subprocess.run([
        FFPROBE, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,nb_frames,pix_fmt",
        "-show_entries", "format=duration,size",
        "-of", "json", mp4,
    ], capture_output=True, text=True, check=True).stdout)

    with open(os.path.join(src, "render-report.json"), "w") as fh:
        json.dump({
            "slug": SLUG,
            "chunks": len(segments),
            "frames": total,
            "encoded_duration_s": round(total / FPS, 3),
            "loop_qc": qc,
            "h264": final,
            "lossless_bytes": os.path.getsize(lossless),
            "prores_bytes": os.path.getsize(mov),
        }, fh, indent=2)

    fs = final["streams"][0]
    print("[encode] h264 %dx%d %s %s frames %ss"
          % (fs["width"], fs["height"], fs["r_frame_rate"],
             fs.get("nb_frames"), final["format"]["duration"]))
    for path in (mp4, mov, sheet, poster):
        print("[encode] %-46s %8.1f MB"
              % (os.path.basename(path), os.path.getsize(path) / (1024 * 1024)))

    if os.path.getsize(mp4) / (1024 ** 3) > 3.9:
        print("[encode] WARNING: H.264 exceeds the 3.9 GB marketplace limit")


if __name__ == "__main__":
    main()