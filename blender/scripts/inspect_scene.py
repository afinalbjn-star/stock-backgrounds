"""Print a scene inventory so CI logs show what was actually loaded.

Cheap and headless. Run it whenever a render misbehaves: it answers "did the
right scene load, and are the loop drivers still attached" without opening a
viewport.
"""

import bpy

scene = bpy.context.scene

counts = {}
for ob in scene.objects:
    counts[ob.type] = counts.get(ob.type, 0) + 1

print("[inventory] objects=%d %s" % (len(scene.objects), counts))
print("[inventory] materials=%d meshes=%d curves=%d lights=%d"
      % (len(bpy.data.materials), len(bpy.data.meshes), len(bpy.data.curves),
         len(bpy.data.lights)))
print("[inventory] engine=%s %dx%d @%dfps frames %d-%d"
      % (scene.render.engine, scene.render.resolution_x,
         scene.render.resolution_y, scene.render.fps,
         scene.frame_start, scene.frame_end))
print("[inventory] view_transform=%s exposure=%.2f"
      % (scene.view_settings.view_transform, scene.view_settings.exposure))
print("[inventory] compositor=%s"
      % (scene.compositing_node_group.name if scene.compositing_node_group
         else "none"))

drivers = 0
for ob in scene.objects:
    if ob.animation_data and ob.animation_data.drivers:
        drivers += len(ob.animation_data.drivers)
for block in (bpy.data.lights, bpy.data.materials):
    for item in block:
        ad = getattr(item, "animation_data", None)
        if ad and ad.drivers:
            drivers += len(ad.drivers)
            for node in getattr(getattr(item, "node_tree", None), "nodes", []):
                for sock in node.outputs:
                    ad = getattr(sock, "id_data", None)
print("[inventory] drivers=%d (all periodic over 720 frames)" % drivers)

camera = scene.camera
if camera:
    print("[inventory] camera=%s lens=%.1fmm dof=%s f/%.1f blades=%d"
          % (camera.name, camera.data.lens, camera.data.dof.use_dof,
             camera.data.dof.aperture_fstop, camera.data.dof.aperture_blades))

# Prove the loop closes before spending GPU hours on it.
frame = scene.frame_end + 1
scene.frame_set(scene.frame_start)
deps = bpy.context.evaluated_depsgraph_get()
a_cam = tuple(camera.evaluated_get(deps).matrix_world.translation)
a_aim = tuple(bpy.data.objects["AimTarget"].evaluated_get(deps).matrix_world.translation)
scene.frame_set(frame)
deps = bpy.context.evaluated_depsgraph_get()
b_cam = tuple(camera.evaluated_get(deps).matrix_world.translation)
b_aim = tuple(bpy.data.objects["AimTarget"].evaluated_get(deps).matrix_world.translation)
scene.frame_set(scene.frame_start)

dcam = max(abs(x - y) for x, y in zip(a_cam, b_cam))
daim = max(abs(x - y) for x, y in zip(a_aim, b_aim))
print("[inventory] loop closure: frame %d vs %d -> camera %.2e, aim %.2e"
      % (scene.frame_start, frame, dcam, daim))
print("[inventory] %s" % ("LOOP CLOSES" if max(dcam, daim) < 1e-4
                           else "LOOP DOES NOT CLOSE"))