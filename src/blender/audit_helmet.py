"""
audit_helmet.py
对 tactical_mech_helmet.blend 做几何与场景预检，输出 audit.json。
数字全部从文件实测，不预填。这是质检报告里所有实测值的来源。
"""
import bpy
import bmesh
import json
import os
import sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = "."
for i, a in enumerate(argv):
    if a == "--out" and i + 1 < len(argv):
        OUT = argv[i + 1]

scene = bpy.context.scene
helmet = bpy.data.collections.get("HELMET")
objs = [o for o in helmet.objects if o.type == "MESH"]

report = {
    "source_file": "tactical_mech_helmet.blend",
    "blender_version": bpy.app.version_string,
    "render_engine": scene.render.engine,
    "render_resolution": [scene.render.resolution_x, scene.render.resolution_y],
    "scene": {},
    "totals": {},
    "objects": [],
}

# ---- 场景级 ----
report["scene"] = {
    "unit_system": scene.unit_settings.system,
    "unit_scale": round(scene.unit_settings.scale_length, 4),
    "camera": scene.camera.name if scene.camera else None,
    "active_lights": sorted(o.name for o in bpy.data.objects if o.type == "LIGHT"),
    "material_count": len(bpy.data.materials),
    "image_textures": len(bpy.data.images),
    "external_files": [img.filepath for img in bpy.data.images if img.source == "FILE"],
}

# ---- 逐对象 + 总计 ----
tot = dict(objects=0, vertices=0, edges=0, faces=0, triangles=0, n_gons=0,
           non_manifold_edges=0, loose_verts=0, loose_edges=0,
           uv_layers=0, uv_missing=0, materials=0, empty_slots=0)
scale_unapplied = []
transforms_unapplied = []
bad_normals = []

for o in objs:
    me = o.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.normal_update()

    nv = len(bm.verts); ne = len(bm.edges); nf = len(bm.faces)
    ntri = sum(max(0, len(f.verts) - 2) for f in bm.faces)
    ngon = sum(1 for f in bm.faces if len(f.verts) > 4)
    nonman = sum(1 for e in bm.edges if not e.is_manifold)
    loosev = sum(1 for v in bm.verts if not v.link_edges)
    loosee = sum(1 for e in bm.edges if not e.link_faces)
    # 面法线与顶点平均法线夹角过大 -> 可能的反转面
    flipped = 0
    for f in bm.faces:
        avg = Vector((0, 0, 0))
        for v in f.verts:
            avg += v.normal
        if avg.length > 0 and f.normal.dot(avg.normalized()) < -0.5:
            flipped += 1

    bm.free()

    uv = len(me.uv_layers)
    mats = sum(1 for m in o.material_slots if m.material)
    empty = sum(1 for m in o.material_slots if not m.material)
    tot["objects"] += 1
    tot["vertices"] += nv
    tot["edges"] += ne
    tot["faces"] += nf
    tot["triangles"] += ntri
    tot["n_gons"] += ngon
    tot["non_manifold_edges"] += nonman
    tot["loose_verts"] += loosev
    tot["loose_edges"] += loosee
    tot["uv_layers"] += uv
    tot["uv_missing"] += 1 if uv == 0 else 0
    tot["materials"] += mats
    tot["empty_slots"] += empty

    # 变换是否已应用（缩放非 1 / 旋转非 0 视为未应用）
    if any(abs(s - 1.0) > 1e-4 for s in o.scale):
        scale_unapplied.append(o.name)
    if any(abs(r) > 1e-4 for r in o.rotation_euler):
        transforms_unapplied.append(o.name)
    if flipped:
        bad_normals.append({"object": o.name, "flipped_faces": flipped})

    report["objects"].append({
        "name": o.name, "vertices": nv, "edges": ne, "faces": nf,
        "triangles": ntri, "n_gons": ngon, "non_manifold_edges": nonman,
        "uv_layers": uv, "material_slots": mats,
    })

tot["scale_unapplied"] = len(scale_unapplied)
tot["rotation_unapplied"] = len(transforms_unapplied)
report["totals"] = tot
report["scale_unapplied_objects"] = sorted(scale_unapplied)
report["rotation_unapplied_objects"] = sorted(transforms_unapplied)
report["possible_flipped_normals"] = bad_normals

os.makedirs(OUT, exist_ok=True)
path = os.path.join(OUT, "audit.json")
with open(path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print("[audit_helmet] 写出:", path)
print("[audit_helmet] 总计:", json.dumps(tot, ensure_ascii=False))
