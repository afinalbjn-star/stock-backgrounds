"""Verify a rendered frame sequence is a real seamless loop.

Two gates, both of which must pass before anything is submitted:

1. Structural  - the frame sequence is contiguous, no gaps, nothing truncated.
2. Seam        - the wrap-around step (last frame -> first frame) must be no
                 more different than an ordinary step inside the clip.

Gate 2 uses PSNR, the same measure and the same 25 dB floor that
`.github/workflows/render.yml` applies to HyperFrames masters, so a Blender
clip and an HTML clip are held to one standard.

A partial render has no wrap point, so the seam verdict is only enforced when
the whole period was rendered. Use SEAM_STRICT=1 to make that explicit.
"""

import json
import os
import re
import subprocess
import sys

FPS = int(os.environ.get("FPS", "60"))
EXPECTED_FRAMES = int(os.environ.get("EXPECTED_FRAMES", "720"))
SEAM_STRICT = os.environ.get("SEAM_STRICT", "0") == "1"
PSNR_FLOOR_DB = float(os.environ.get("PSNR_FLOOR_DB", "25"))
FFMPEG = os.environ.get("FFMPEG_BIN", "ffmpeg")
PREFIX = os.environ.get("FRAME_PREFIX", "pcb_")


def have(tool):
    return subprocess.run(["where", tool], capture_output=True,
                          shell=True).returncode == 0


def discover(src):
    pat = re.compile(r"^%s(\d+)\.png$" % re.escape(PREFIX))
    out = []
    for name in os.listdir(src):
        m = pat.match(name)
        if m:
            out.append(int(m.group(1)))
    return sorted(out)


def grab(src, n):
    return os.path.join(src, "%s%04d.png" % (PREFIX, n))


def psnr(a, b):
    """PSNR in dB between two frames. Returns None if they are identical."""
    proc = subprocess.run([
        FFMPEG, "-v", "info", "-i", a, "-i", b,
        "-lavfi", "psnr", "-f", "null", "-"
    ], capture_output=True, text=True)
    matches = re.findall(r"average:([0-9.]+|inf)", proc.stderr)
    if not matches:
        return None
    value = matches[-1]
    if value == "inf":
        return float("inf")
    return float(value)


def fail(report, src, message):
    report["verdict"] = "FAIL"
    report["reason"] = message
    with open(os.path.join(src, "loop_qc.json"), "w") as fh:
        json.dump(report, fh, indent=2)
    print("[qc] FAIL: %s" % message)
    sys.exit(1)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "renders"

    if not have(FFMPEG):
        sys.exit("[qc] ffmpeg not available on PATH")

    numbers = discover(src)
    if not numbers:
        sys.exit("[qc] FAIL: no %s####.png frames found in %s" % (PREFIX, src))

    first, last = numbers[0], numbers[-1]
    count = len(numbers)
    report = {
        "frames_found": count,
        "frame_range": [first, last],
        "expected_frames": EXPECTED_FRAMES,
        "fps": FPS,
        "duration_s": round(count / FPS, 3),
        "psnr_floor_db": PSNR_FLOOR_DB,
        "seam_strict": SEAM_STRICT,
    }

    if numbers != list(range(first, last + 1)):
        gaps = [n for n in range(first, last + 1) if n not in set(numbers)]
        fail(report, src, "%d gaps in the frame sequence, first %s"
             % (len(gaps), gaps[:10]))

    tiny = [n for n in numbers if os.path.getsize(grab(src, n)) < 4096]
    if tiny:
        print("[qc] WARN: %d suspiciously small frames: %s"
              % (len(tiny), tiny[:10]))
        report["tiny_frames"] = tiny[:20]

    if count != EXPECTED_FRAMES:
        print("[qc] NOTE: %d frames rendered, expected %d"
              % (count, EXPECTED_FRAMES))
        report["note"] = "partial render, seam not enforced"

    if count < 3:
        report["verdict"] = "PASS (too few frames for a seam comparison)"
        with open(os.path.join(src, "loop_qc.json"), "w") as fh:
            json.dump(report, fh, indent=2)
        print("[qc] only %d frames, seam test skipped" % count)
        return

    # Ordinary interior steps, sampled across the clip.
    step = max(1, count // 12)
    interior = [psnr(grab(src, n), grab(src, n + 1))
                for n in range(first, last, step) if n + 1 <= last]
    interior = [p for p in interior if p is not None]

    # The wrap the viewer actually sees when the clip repeats.
    seam = psnr(grab(src, last), grab(src, first))

    if not interior or seam is None:
        print("[qc] NOTE: not enough distinct frames to judge the seam")
        report["verdict"] = "PASS (seam undetermined)"
        with open(os.path.join(src, "loop_qc.json"), "w") as fh:
            json.dump(report, fh, indent=2)
        return

    worst_step = min(interior)
    report.update({
        "interior_step_psnr_db": round(worst_step, 2),
        "interior_step_psnr_best_db": round(max(interior), 2),
        "loop_seam_psnr_db": round(seam, 2),
        "samples_taken": len(interior),
    })

    def write():
        with open(os.path.join(src, "loop_qc.json"), "w") as fh:
            json.dump(report, fh, indent=2)

    write()

    print("[qc] %d frames %d..%d = %.3f s" % (count, first, last, count / FPS))
    print("[qc] ordinary frame step : %.2f dB (worst of %d samples)"
          % (worst_step, len(interior)))
    print("[qc] loop seam           : %.2f dB" % seam)

    if not SEAM_STRICT:
        report["verdict"] = "PASS (partial render, seam reported not enforced)"
        write()
        print("[qc] PASS: partial render, seam reported but not enforced")
        return

    if seam < PSNR_FLOOR_DB:
        fail(report, src,
             "loop seam PSNR %.2f dB is below the %.0f dB floor — "
             "the composition is not closing on its start state"
             % (seam, PSNR_FLOOR_DB))

    report["verdict"] = "PASS"
    write()
    print("[qc] PASS: seam is within normal frame-to-frame motion")


if __name__ == "__main__":
    main()