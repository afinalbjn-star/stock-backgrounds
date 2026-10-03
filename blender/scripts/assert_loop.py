"""Refuse to spend runner time on a scene whose loop does not close.

The wrap point of a stock loop is the transition from the last frame back to
the first. If that transition is larger than an ordinary step inside the clip,
the loop reads as a cut.

This script compares the animated state at frame 1 against frame
`period + 1`, which must be identical when the driver period equals the clip
period. It runs headless in about two seconds, so it belongs in front of a
360-frame render, not after it.

The 720-frame authoring bug this guards against: the drivers were built on
2*pi/720 while the clip was 360 frames at 30 fps. That covers half a cycle,
so frame 360 sat at camera z = 7.25 while frame 1 sat at z = 9.55. Measured
on the rendered result, the seam came out at 13.3 dB against a 21.5 dB
ordinary step.
"""

import sys

import bpy

TOLERANCE = 1e-4

scene = bpy.context.scene
period = scene.frame_end
if period < 1:
    sys.exit("[assert_loop] scene has no frames")

camera = scene.camera
target = bpy.data.objects.get("AimTarget")

lights = [o for o in sorted(scene.objects, key=lambda x: x.name)
          if o.type == "LIGHT"]


def state(frame):
    scene.frame_set(frame)
    return {
        "camera": tuple(camera.matrix_world.translation),
        "camera_rot": tuple(camera.matrix_world.to_euler()),
        "lens": camera.data.lens,
        "focus": camera.data.dof.focus_distance if camera.data.dof.use_dof else 0.0,
        "aim": tuple(target.matrix_world.translation) if target else (0.0, 0.0, 0.0),
        "lights": tuple(o.data.energy for o in lights),
    }


first = state(1)
wrap = state(period + 1)

worst = 0.0
worst_key = ""
for key, a in first.items():
    b = wrap[key]
    pairs = zip(a, b) if isinstance(a, tuple) else [(a, b)]
    for x, y in pairs:
        delta = abs(x - y)
        if delta > worst:
            worst = delta
            worst_key = key

print("[assert_loop] clip is frames 1-%d at %d fps = %.3f s"
      % (period, scene.render.fps, period / scene.render.fps))
print("[assert_loop] driver period should equal the clip period")
print("[assert_loop] camera @1    = %s" % (tuple(round(v, 5) for v in first["camera"]),))
print("[assert_loop] camera @%d = %s" % (period + 1,
                                         tuple(round(v, 5) for v in wrap["camera"])))
print("[assert_loop] worst difference = %.9f on %s" % (worst, worst_key))

scene.frame_set(1)

if worst > TOLERANCE:
    print("[assert_loop] FAIL: the wrap differs by %.9f, tolerance %.0e. "
          "The loop will read as a cut." % (worst, TOLERANCE))
    print("[assert_loop] Every driver must be a function of "
          "sin((frame-1) * 2*pi / %d) at integer harmonics." % period)
    sys.exit(1)

print("[assert_loop] PASS: frame %d reproduces frame 1 exactly" % (period + 1))
