"""
export_glb.py
只把 HELMET 集合里的资产导出为 GLB，排除 STUDIO 的灯光/相机/背景。
用于网页端实时预览，不影响 .blend 源文件。
"""
import bpy
import os
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = "."
for i, a in enumerate(argv):
    if a == "--out" and i + 1 < len(argv):
        OUT = argv[i + 1]

# 只选中 HELMET 集合的对象
bpy.ops.object.select_all(action="DESELECT")
helmet = bpy.data.collections.get("HELMET")
for o in helmet.objects:
    o.select_set(True)
bpy.context.view_layer.objects.active = next(iter(helmet.objects))

path = os.path.join(OUT, "helmet.glb")
bpy.ops.export_scene.gltf(
    filepath=path,
    export_format="GLB",
    use_selection=True,
    export_materials="EXPORT",
    export_cameras=False,
    export_lights=False,
    export_yup=True,
    export_apply=False,
)
print("[export_glb] 导出:", path, os.path.getsize(path), "bytes")
