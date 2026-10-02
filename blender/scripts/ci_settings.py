"""Apply CI render overrides, read from environment variables.

Run before the animation render:

    ENGINE=cycles SAMPLES=64 START_FRAME=1 END_FRAME=20 SEGMENT_DIR=renders \\
        blender -b scene.blend -P ci_settings.py -a

Keeping this in a file rather than a `--python-expr` string avoids the shell
and YAML quoting that would otherwise mangle the code.

The scene was authored so that every animated quantity is a function of
sin((frame - 1) * 2*pi/720) at an integer harmonic. That is what makes frame
721 reproduce frame 1, so this script never touches keyframes: it only sets
resolution, frame range, sampling and output path.

Output is a lossless FFV1 segment in Matroska, not a PNG sequence. A 720-frame
4K 16-bit PNG run is about 19 GB and has to be uploaded as 36 artifacts; the
same frames as FFV1 are roughly 300 MB in total, and they can be concatenated
with a stream copy instead of re-encoded.
"""

import os

import bpy

FRAME_START = int(os.environ.get("START_FRAME", "1"))
FRAME_END = int(os.environ.get("END_FRAME", "720"))
SAMPLES = int(os.environ.get("SAMPLES", "64"))
ENGINE = os.environ.get("ENGINE", "cycles")
SEGMENT_DIR = os.environ.get("SEGMENT_DIR", "renders")
CHUNK_INDEX = os.environ.get("CHUNK_INDEX", "000")
RES_X = int(os.environ.get("RES_X", "3840"))
RES_Y = int(os.environ.get("RES_Y", "2160"))
FPS = int(os.environ.get("FPS", "60"))

scene = bpy.context.scene
render = scene.render

render.engine = "CYCLES" if ENGINE == "cycles" else "BLENDER_EEVEE"
render.resolution_x = RES_X
render.resolution_y = RES_Y
render.resolution_percentage = 100
render.fps = FPS
render.fps_base = 1.0

scene.frame_start = FRAME_START
scene.frame_end = FRAME_END

# --- lossless video output ---
image = render.image_settings
if "media_type" in image.bl_rna.properties:
    image.media_type = "VIDEO"
image.file_format = "FFMPEG"

ff = render.ffmpeg
ff.format = "MKV"
ff.codec = "FFV1"
ff.constant_rate_factor = "LOSSLESS"
ff.use_lossless_output = True
ff.ffmpeg_preset = "GOOD"
ff.gopsize = 1          # every frame a keyframe: any segment start cuts cleanly
ff.audio_codec = "NONE"

render.use_overwrite = True
render.use_file_extension = True
render.use_placeholder = False
render.filepath = os.path.join(SEGMENT_DIR, "seg_%s_" % CHUNK_INDEX)

if render.engine == "CYCLES":
    cy = scene.cycles
    cy.device = "CPU"           # GitHub runners have no GPU
    cy.samples = SAMPLES
    cy.preview_samples = 16
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.02
    cy.use_denoising = True
    cy.max_bounces = 4
    cy.diffuse_bounces = 2
    cy.glossy_bounces = 3
    cy.transmission_bounces = 0
    cy.transparent_max_bounces = 4
    cy.volume_bounces = 0
    cy.caustics_reflective = False
    cy.caustics_refractive = False
    cy.blur_glossy = 2.0
    cy.sample_clamp_indirect = 6.0
    cy.use_light_tree = True
    # Multi-tiling keeps every runner core busy on a 4K frame.
    cy.use_auto_tile = True
    cy.tile_size = 2048
else:
    ee = scene.eevee
    ee.taa_render_samples = max(SAMPLES, 32)
    if hasattr(ee, "use_raytracing"):
        ee.use_raytracing = True

scene.view_settings.view_transform = "AgX"
scene.view_settings.gamma = 1.0

counts = {}
for ob in scene.objects:
    counts[ob.type] = counts.get(ob.type, 0) + 1

drivers = 0
for ob in scene.objects:
    if ob.animation_data and ob.animation_data.drivers:
        drivers += len(ob.animation_data.drivers)

print("[ci_settings] engine=%s %dx%d @%dfps frames %d-%d samples=%d"
      % (render.engine, RES_X, RES_Y, FPS, FRAME_START, FRAME_END, SAMPLES))
print("[ci_settings] objects=%d %s" % (len(scene.objects), counts))
print("[ci_settings] materials=%d meshes=%d curves=%d object-drivers=%d"
      % (len(bpy.data.materials), len(bpy.data.meshes), len(bpy.data.curves),
         drivers))
print("[ci_settings] output=%s (%s/%s lossless)"
      % (render.filepath, ff.codec, ff.format))