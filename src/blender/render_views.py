"""
render_views.py
从 tactical_mech_helmet.blend 渲染主视觉与四种质检取证图。

用法:
  blender -b tactical_mech_helmet.blend --python render_views.py -- \
      --mode hero|wire|normals|uv --out /path --res 7680x4320 --samples 64

说明：所有视图共用同一台相机与布光，保证取证图与主视觉机位一致，
方便核对"截图与源文件是否同一资产"。脚本只读场景，不保存 .blend。
"""
import bpy
import sys
import os

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = "hero"
OUT = "."
RES = "1280x720"
SAMPLES = 48
for i, a in enumerate(argv):
    if a == "--mode" and i + 1 < len(argv): MODE = argv[i + 1]
    elif a == "--out" and i + 1 < len(argv): OUT = argv[i + 1]
    elif a == "--res" and i + 1 < len(argv): RES = argv[i + 1]
    elif a == "--samples" and i + 1 < len(argv): SAMPLES = int(argv[i + 1])

w, h = (int(x) for x in RES.lower().split("x"))
scene = bpy.context.scene
helmet = bpy.data.collections.get("HELMET")

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.resolution_x = w
scene.render.resolution_y = h
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass


def emission_mat(name, color):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*color, 1)
    nt.links.new(e.outputs[0], o.inputs["Surface"])
    return m


def normals_mat():
    m = bpy.data.materials.new("QA_NormalVisualize")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    e = nt.nodes.new("ShaderNodeEmission")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    # 世界空间法线 -> 相机空间，得到标准法线图的蓝/绿/红配色
    tf = nt.nodes.new("ShaderNodeVectorTransform")
    tf.vector_type = "VECTOR"
    tf.convert_from = "WORLD"
    tf.convert_to = "CAMERA"
    vec = nt.nodes.new("ShaderNodeVectorMath")
    vec.operation = "MULTIPLY_ADD"
    vec.inputs[1].default_value = (0.5, 0.5, 0.5)
    vec.inputs[2].default_value = (0.5, 0.5, 0.5)
    nt.links.new(geo.outputs["Normal"], tf.inputs["Vector"])
    nt.links.new(tf.outputs["Vector"], vec.inputs[0])
    nt.links.new(vec.outputs["Vector"], e.inputs["Color"])
    nt.links.new(e.outputs[0], o.inputs["Surface"])
    return m


def uv_checker_mat():
    m = bpy.data.materials.new("QA_UVChecker")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    e = nt.nodes.new("ShaderNodeEmission")
    tex = nt.nodes.new("ShaderNodeTexChecker")
    tex.inputs["Scale"].default_value = 8.0
    tex.inputs["Color1"].default_value = (0.92, 0.92, 0.92, 1)
    tex.inputs["Color2"].default_value = (0.08, 0.09, 0.11, 1)
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    nt.links.new(uv.outputs["UV"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], e.inputs["Color"])
    nt.links.new(e.outputs[0], o.inputs["Surface"])
    return m


mesh_objs = [o for o in helmet.objects if o.type == "MESH"] if helmet else []

if MODE == "wire":
    # 拓扑检查聚焦主体装甲板布线：隐藏铆钉/螺丝/线缆等细碎五金件，
    # 否则上千个小件的网格会叠在一起看不清走向。
    tiny_prefix = ("Rivet_", "Socket_", "Cable_", "Cable_Upper", "Vent_",
                   "Hydraulic_", "Ear_Screw", "Ear_Ring", "Antenna_",
                   "Respirator_", "Sensor_")
    for o in mesh_objs:
        if o.name.startswith(tiny_prefix) or o.name.startswith("Inner_Seal_Liner"):
            o.hide_render = True
    wiremat = emission_mat("QA_Wire", (0.30, 0.95, 0.88))
    for o in mesh_objs:
        if o.hide_render:
            continue
        o.data.materials.clear()
        o.data.materials.append(wiremat)
        mod = o.modifiers.new("QA_Wireframe", "WIREFRAME")
        mod.thickness = 0.0035
        mod.use_replace = True
elif MODE == "normals":
    nm = normals_mat()
    for o in mesh_objs:
        o.data.materials.clear()
        o.data.materials.append(nm)
elif MODE == "uv":
    um = uv_checker_mat()
    for o in mesh_objs:
        # 基础体自带 UVMap，曲面装甲板也生成了 UVMap
        o.data.materials.clear()
        o.data.materials.append(um)

scene.render.filepath = os.path.join(OUT, "%s.png" % MODE)
bpy.ops.render.render(write_still=True)
print("[render_views] 完成:", scene.render.filepath, RES, "samples", SAMPLES)
