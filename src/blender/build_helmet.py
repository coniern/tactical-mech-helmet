"""
build_helmet.py
战术机甲头盔 — 几何构建脚本

做法：先把头盔想成一颗椭球，用参数化的「曲面装甲板」生成器把不同区域
一块块贴在椭球面上。这样每块板都是干净的四边面，倒角只发生在板的外缘，
不会出现布尔运算遗留的乱线。机械细节再用圆柱、立方体、曲线这些基础体
堆上去，全部按功能命名，方便后面打开源文件逐项检查。

用法:
  blender -b --factory-startup --python build_helmet.py -- --out /path/to/repo
"""

import bpy
import math
import os
import sys
from mathutils import Vector

# ---------------------------------------------------------------------------
# 参数
# ---------------------------------------------------------------------------
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = "."
for i, a in enumerate(argv):
    if a == "--out" and i + 1 < len(argv):
        OUT = argv[i + 1]

BASE = (0.92, 1.06, 1.02)      # 椭球三轴半径：x 宽、y 深、z 高
PLATE_OFFSET = 0.014           # 装甲板相对内壳的外移量
PLATE_THICK = 0.026            # 装甲板厚度
BEVEL = 0.0055                 # 板外缘倒角

# ---------------------------------------------------------------------------
# 场景初始化
# ---------------------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for datablocks in (bpy.data.meshes, bpy.data.materials, bpy.data.curves):
    for block in list(datablocks):
        if block.users == 0:
            datablocks.remove(block)

helmet_col = bpy.data.collections.new("HELMET")
studio_col = bpy.data.collections.new("STUDIO")
bpy.context.scene.collection.children.link(helmet_col)
bpy.context.scene.collection.children.link(studio_col)


def link_helmet(obj):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    helmet_col.objects.link(obj)
    return obj


def link_studio(obj):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    studio_col.objects.link(obj)
    return obj


# ---------------------------------------------------------------------------
# 材质
# ---------------------------------------------------------------------------
def set_input(node, name, value):
    if name in node.inputs:
        node.inputs[name].default_value = value


def make_material(name, base, metallic, roughness, *,
                  emission=None, emission_strength=0.0,
                  brushed=False, coat=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (520, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (220, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    set_input(bsdf, "Base Color", (*base, 1.0))
    set_input(bsdf, "Metallic", metallic)
    set_input(bsdf, "Roughness", roughness)
    set_input(bsdf, "Coat Weight", coat)
    set_input(bsdf, "Coat Roughness", 0.12)

    if brushed:
        # 拉丝：把噪声在一个方向上压扁，得到细长条纹，再接到法线
        tex = nt.nodes.new("ShaderNodeTexNoise")
        tex.location = (-620, -160)
        tex.inputs["Scale"].default_value = 1.0
        tex.inputs["Detail"].default_value = 2.0
        mapn = nt.nodes.new("ShaderNodeMapping")
        mapn.location = (-420, -160)
        mapn.inputs["Scale"].default_value = (240.0, 6.0, 6.0)
        nt.links.new(tex.outputs["Fac"], mapn.inputs["Vector"]) if False else None
        coord = nt.nodes.new("ShaderNodeTexCoord")
        coord.location = (-820, -160)
        nt.links.new(coord.outputs["Generated"], mapn.inputs["Vector"])
        nt.links.new(mapn.outputs["Vector"], tex.inputs["Vector"])
        bump = nt.nodes.new("ShaderNodeBump")
        bump.location = (-60, -160)
        bump.inputs["Strength"].default_value = 0.16
        bump.inputs["Distance"].default_value = 0.006
        nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        try:
            set_input(bsdf, "Anisotropic IOR Level", 0.55)
        except Exception:
            pass

    if emission:
        set_input(bsdf, "Emission Color", (*emission, 1.0))
        set_input(bsdf, "Emission Strength", emission_strength)
    return mat


MAT = {
    "titanium": make_material("M_Ti_Gunmetal_Dark", (0.098, 0.110, 0.124), 0.96, 0.37, coat=0.18),
    "brushed":  make_material("M_Ti_Brushed", (0.168, 0.182, 0.198), 0.94, 0.29, brushed=True),
    "ceramic":  make_material("M_Ceramic_Matte", (0.150, 0.158, 0.170), 0.08, 0.72),
    "steel":    make_material("M_Steel_Hardware", (0.072, 0.078, 0.090), 0.88, 0.38),
    "black":    make_material("M_Cavity_Black", (0.010, 0.011, 0.014), 0.20, 0.88),
    "rubber":   make_material("M_Rubber_Seal", (0.020, 0.022, 0.026), 0.0, 0.86),
    "visor":    make_material("M_Visor_Smoked", (0.016, 0.024, 0.036), 1.0, 0.055, coat=0.85),
    "orange":   make_material("M_Orange_Warning", (0.78, 0.235, 0.028), 0.22, 0.40,
                              emission=(0.42, 0.10, 0.008), emission_strength=0.35),
    "led_cyan": make_material("M_LED_Cyan", (0.02, 0.08, 0.10), 0.0, 0.25,
                              emission=(0.06, 0.72, 1.0), emission_strength=5.5),
    "led_amber":make_material("M_LED_Amber", (0.10, 0.05, 0.01), 0.0, 0.25,
                              emission=(1.0, 0.38, 0.04), emission_strength=4.0),
    "floor":    make_material("M_Studio_Floor", (0.031, 0.035, 0.043), 0.12, 0.62),
}

# ---------------------------------------------------------------------------
# 椭球面工具
# ---------------------------------------------------------------------------
def surf(u, v, offset=0.0):
    """返回椭球面上 (水平角 u, 高度 v) 的位置与外法线。u=0 是正前方(-Y)。"""
    h = max(-0.985, min(0.985, v / BASE[2]))
    r = math.sqrt(max(0.0, 1.0 - h * h))
    x = BASE[0] * r * math.sin(u)
    y = -BASE[1] * r * math.cos(u)
    z = v
    p = Vector((x, y, z))
    n = Vector((x / (BASE[0] ** 2), y / (BASE[1] ** 2), z / (BASE[2] ** 2)))
    if n.length < 1e-6:
        n = Vector((0, -1, 0))
    n.normalize()
    return p + n * offset, n


def shell_plate(name, u0, u1, v0, v1, nu, nv, mat, *,
                offset=PLATE_OFFSET, thickness=PLATE_THICK, bevel=BEVEL,
                uv_scale=1.6):
    """在椭球面上生成一块弯曲装甲板；全四边面，外缘倒角。"""
    verts, params = [], []
    for j in range(nv + 1):
        v = v0 + (v1 - v0) * j / nv
        for i in range(nu + 1):
            u = u0 + (u1 - u0) * i / nu
            p, _ = surf(u, v, offset)
            verts.append(p)
            params.append((u, v))
    faces = []
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            faces.append((a, a + 1, a + nu + 2, a + nu + 1))

    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    uv = mesh.uv_layers.new(name="UVMap")
    for li, loop in enumerate(mesh.loops):
        u, v = params[loop.vertex_index]
        uv.data[li].uv = (u * uv_scale, v * uv_scale)

    obj = bpy.data.objects.new(name, mesh)
    helmet_col.objects.link(obj)
    obj.data.materials.append(mat)

    if thickness > 0:
        mod = obj.modifiers.new("shell_thickness", "SOLIDIFY")
        mod.thickness = thickness
        mod.offset = -1.0
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
    if bevel > 0:
        mod = obj.modifiers.new("edge_bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        mod.limit_method = "ANGLE"
        mod.angle_limit = math.radians(32)
        bpy.ops.object.modifier_apply(modifier=mod.name)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def prim_cube(name, location, scale, mat, rot=None, bevel=0.0, col=helmet_col):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    if rot is not None:
        o.rotation_euler = rot
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for c in list(o.users_collection):
        c.objects.unlink(o)
    col.objects.link(o)
    o.data.materials.append(mat)
    if bevel > 0:
        mod = o.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return o


def prim_cyl(name, location, radius, depth, mat, vertices=20, direction=None, col=helmet_col):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location)
    o = bpy.context.object
    o.name = name
    if direction is not None:
        o.rotation_euler = direction.normalized().to_track_quat("Z", "Y").to_euler()
    for c in list(o.users_collection):
        c.objects.unlink(o)
    col.objects.link(o)
    o.data.materials.append(mat)
    return o


def prim_sphere(name, location, radius, mat, segments=16, rings=10, col=helmet_col):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=radius, location=location)
    o = bpy.context.object
    o.name = name
    for c in list(o.users_collection):
        c.objects.unlink(o)
    col.objects.link(o)
    o.data.materials.append(mat)
    return o


# ---------------------------------------------------------------------------
# 1. 内壳：一层极黑的密封胆，装甲板之间的缝隙露出它
# ---------------------------------------------------------------------------
inner = prim_sphere("Inner_Seal_Liner", (0, 0, 0), 1.0, MAT["rubber"], segments=48, rings=32)
inner.scale = BASE
bpy.context.view_layer.objects.active = inner
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
for p in inner.data.polygons:
    p.use_smooth = True

# ---------------------------------------------------------------------------
# 2. 面罩与框
# ---------------------------------------------------------------------------
visor = shell_plate("Visor_Smoked_Panel", -0.86, 0.86, -0.36, 0.20, 26, 14,
                    MAT["visor"], offset=PLATE_OFFSET + 0.004, thickness=0.018,
                    bevel=0.003, uv_scale=1.2)

for nm, u0, u1, v0, v1 in [
    ("Visor_Frame_Top",    -0.93, 0.93,  0.195, 0.265),
    ("Visor_Frame_Bottom", -0.93, 0.93, -0.425, -0.355),
    ("Visor_Frame_L",       0.86, 0.94, -0.36,  0.20),
    ("Visor_Frame_R",      -0.94, -0.86, -0.36,  0.20),
]:
    shell_plate(nm, u0, u1, v0, v1, max(3, int((u1 - u0) * 16)), max(2, int((v1 - v0) * 40)),
                MAT["steel"], offset=PLATE_OFFSET + 0.008, thickness=0.022, bevel=0.003)

# 眉骨上方一条橙色警示线
shell_plate("Warning_Brow_Line", -0.50, 0.50, 0.272, 0.292, 20, 1,
            MAT["orange"], offset=PLATE_OFFSET + 0.011, thickness=0.006, bevel=0.0012, uv_scale=2.4)

# ---------------------------------------------------------------------------
# 3. 主要装甲板
# ---------------------------------------------------------------------------
plates = [
    # name,                 u0,    u1,    v0,    v1,     nu, nv, material
    ("Crown_Main_Plate",   -1.75,  1.75,  0.585, 0.965, 44, 10, "titanium"),
    ("Forehead_Armor",     -0.94,  0.94,  0.300, 0.575, 26, 8,  "brushed"),
    ("Temple_L",            0.98,  1.62,  0.28,  0.62,  12, 8,  "titanium"),
    ("Temple_R",           -1.62, -0.98,  0.28,  0.62,  12, 8,  "titanium"),
    ("Cheek_L",             0.96,  1.92, -0.42,  0.24,  20, 14, "ceramic"),
    ("Cheek_R",            -1.92, -0.96, -0.42,  0.24,  20, 14, "ceramic"),
    ("Jaw_Armor",          -0.90,  0.90, -0.80, -0.44,  24, 9,  "titanium"),
    ("Occipital_Plate",     2.05,  4.23, -0.18,  0.72,  38, 18, "titanium"),
    ("Nape_Plate",          2.10,  4.18, -0.72, -0.21,  34, 10, "brushed"),
]
for nm, u0, u1, v0, v1, nu, nv, mk in plates:
    shell_plate(nm, u0, u1, v0, v1, nu, nv, MAT[mk])

# 头顶纵向脊线：拉丝 titanium 条，两侧用深钢包边
shell_plate("Crest_Brushed_Strip", -0.115, 0.115, 0.60, 0.955, 5, 12,
            MAT["brushed"], offset=PLATE_OFFSET + 0.016, thickness=0.014, bevel=0.0025)
for uu in (-0.135, 0.135):
    shell_plate("Crest_Edge_%s" % ("L" if uu > 0 else "R"), uu - 0.014, uu + 0.014,
                0.60, 0.955, 2, 12, MAT["steel"],
                offset=PLATE_OFFSET + 0.014, thickness=0.010, bevel=0.0018)

# 前额中央橙色竖条
shell_plate("Warning_Forehead_Center", -0.045, 0.045, 0.315, 0.555, 2, 10,
            MAT["orange"], offset=PLATE_OFFSET + 0.017, thickness=0.006,
            bevel=0.0011, uv_scale=3.0)

# 左右脸颊的橙色斜条
for sgn, tag in ((1, "L"), (-1, "R")):
    shell_plate("Warning_Cheek_%s" % tag, sgn * 1.72, sgn * 1.66, -0.30, 0.10, 2, 8,
                MAT["orange"], offset=PLATE_OFFSET + 0.016, thickness=0.006,
                bevel=0.0011, uv_scale=3.0)

# ---------------------------------------------------------------------------
# 4. 铆钉：共享网格 + 实例化，每颗带一个深色内六角凹槽
# ---------------------------------------------------------------------------
bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.017, depth=0.011)
RIVET_MESH = bpy.context.object.data
bpy.data.objects.remove(bpy.context.object, do_unlink=True)
RIVET_MESH.materials.append(MAT["steel"])
bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.0085, depth=0.0015)
SOCKET_MESH = bpy.context.object.data
bpy.data.objects.remove(bpy.context.object, do_unlink=True)
SOCKET_MESH.materials.append(MAT["black"])

rivet_count = 0

def rivet(u, v, tag=""):
    global rivet_count
    p, n = surf(u, v, PLATE_OFFSET + 0.043)
    q = n.to_track_quat("Z", "Y").to_euler()
    r = bpy.data.objects.new("Rivet_%03d" % rivet_count, RIVET_MESH)
    helmet_col.objects.link(r)
    r.location = p - n * 0.004
    r.rotation_euler = q
    s = bpy.data.objects.new("Socket_%03d" % rivet_count, SOCKET_MESH)
    helmet_col.objects.link(s)
    s.location = p + n * 0.0018
    s.rotation_euler = q
    rivet_count += 1

# 沿各板边缘布点
edge_specs = [
    (-0.92, 0.92, 0.585, 0.585, 14), (-0.92, 0.92, 0.96, 0.96, 14),
    (-0.94, -0.94, 0.30, 0.575, 6), (0.94, 0.94, 0.30, 0.575, 6),
    (0.98, 1.62, 0.60, 0.60, 6), (-1.62, -0.98, 0.60, 0.60, 6),
    (0.96, 1.92, 0.22, 0.22, 10), (-1.92, -0.96, 0.22, 0.22, 10),
    (0.96, 1.92, -0.40, -0.40, 10), (-1.92, -0.96, -0.40, -0.40, 10),
    (-0.88, 0.88, -0.78, -0.78, 12),
    (2.10, 4.18, 0.70, 0.70, 14), (2.10, 4.18, -0.70, -0.70, 14),
]
for u0, u1, v0, v1, n in edge_specs:
    for i in range(n + 1):
        t = i / n
        rivet(u0 + (u1 - u0) * t, v0 + (v1 - v0) * t)

# ---------------------------------------------------------------------------
# 5. 散热格栅
# ---------------------------------------------------------------------------
def vent(name, u0, u1, v0, v1, rows, mat_dark, mat_frame):
    """在一块板表面上排一列细长凹槽，外加一圈金属压边。"""
    umid = (u0 + u1) * 0.5
    p, n = surf(umid, (v0 + v1) * 0.5, PLATE_OFFSET + 0.021)
    q = n.to_track_quat("Z", "Y").to_euler()
    arc = abs(u1 - u0) * (BASE[0] + BASE[1]) * 0.5
    span = abs(v1 - v0)
    for k in range(rows):
        v = v0 + (v1 - v0) * (k + 0.5) / rows
        pk, nk = surf(umid, v, PLATE_OFFSET + 0.022)
        o = prim_cube("%s_Slot_%02d" % (name, k + 1), pk,
                      (arc * 0.86, span / rows * 0.42, 0.006), mat_dark,
                      rot=nk.to_track_quat("Z", "Y").to_euler())
    for vv in (v0 - span * 0.06, v1 + span * 0.06):
        pk, nk = surf(umid, vv, PLATE_OFFSET + 0.022)
        prim_cube("%s_Edge" % name, pk,
                  (arc * 1.02, span * 0.07, 0.008), mat_frame,
                  rot=nk.to_track_quat("Z", "Y").to_euler())
    for uu in (u0 - 0.035, u1 + 0.035):
        pk, nk = surf(uu, (v0 + v1) * 0.5, PLATE_OFFSET + 0.022)
        prim_cube("%s_Side" % name, pk,
                  (span * 0.10, span * 1.14, 0.008), mat_frame,
                  rot=nk.to_track_quat("Z", "Y").to_euler())

vent("Vent_Cheek_L", 1.12, 1.78, 0.00, 0.17, 5, MAT["black"], MAT["steel"])
vent("Vent_Cheek_R", -1.78, -1.12, 0.00, 0.17, 5, MAT["black"], MAT["steel"])
vent("Vent_Jaw_L", 0.30, 0.74, -0.70, -0.55, 4, MAT["black"], MAT["steel"])
vent("Vent_Jaw_R", -0.74, -0.30, -0.70, -0.55, 4, MAT["black"], MAT["steel"])
vent("Vent_Occiput", 2.45, 3.85, 0.20, 0.52, 7, MAT["black"], MAT["steel"])

# ---------------------------------------------------------------------------
# 6. 外露机械结构：耳部模组、液压杆、呼吸器、传感器
# ---------------------------------------------------------------------------
# 耳部圆形模组
for sgn, tag in ((1, "L"), (-1, "R")):
    center, normal = surf(sgn * 1.90, -0.10, PLATE_OFFSET + 0.035)
    q = normal.to_track_quat("Z", "Y")
    base = prim_cyl("Ear_Housing_%s" % tag, center, 0.145, 0.055, MAT["steel"],
                    vertices=32, direction=normal)
    for k, (rad, dep, mk) in enumerate([
        (0.118, 0.012, MAT["brushed"]),
        (0.092, 0.010, MAT["black"]),
        (0.062, 0.014, MAT["titanium"]),
    ]):
        pk = center + normal * (0.030 + k * 0.014)
        prim_cyl("Ear_Ring_%s_%d" % (tag, k + 1), pk, rad, dep, mk,
                 vertices=32, direction=normal)
    prim_cyl("Ear_Lens_%s" % tag, center + normal * 0.078, 0.032, 0.012,
             MAT["led_cyan"], vertices=24, direction=normal)
    # 外圈六颗小螺丝
    for i in range(6):
        a = i * math.pi / 3
        t = Vector((math.cos(a), math.sin(a), 0))
        tangent = q @ t
        pk = center + tangent * 0.128 + normal * 0.032
        prim_cyl("Ear_Screw_%s_%d" % (tag, i + 1), pk, 0.012, 0.008,
                 MAT["steel"], vertices=6, direction=normal)

# 两侧液压杆：从太阳穴斜向后脑
for sgn, tag in ((1, "L"), (-1, "R")):
    p1, _ = surf(sgn * 1.46, 0.34, PLATE_OFFSET + 0.052)
    p2, _ = surf(sgn * 2.62, 0.56, PLATE_OFFSET + 0.052)
    mid = (p1 + p2) * 0.5
    d = p2 - p1
    prim_cyl("Hydraulic_Rod_%s" % tag, mid, 0.026, d.length, MAT["brushed"],
             vertices=16, direction=d)
    prim_cyl("Hydraulic_Sleeve_%s" % tag, p1 + d * 0.28, 0.042, d.length * 0.42,
             MAT["steel"], vertices=16, direction=d)
    for k, pp in enumerate((p1, p2)):
        prim_sphere("Hydraulic_Joint_%s_%d" % (tag, k + 1), pp, 0.048,
                    MAT["steel"], segments=16, rings=10)
        prim_cyl("Hydraulic_Pin_%s_%d" % (tag, k + 1), pp + Vector((0, 0, 0.055)),
                 0.020, 0.085, MAT["titanium"], vertices=12)

# 呼吸器：下颌中央同心结构
resp, resp_n = surf(0.0, -0.60, PLATE_OFFSET + 0.045)
for k, (rad, dep, mk) in enumerate([
    (0.19, 0.030, MAT["steel"]),
    (0.155, 0.014, MAT["brushed"]),
    (0.125, 0.020, MAT["black"]),
    (0.095, 0.016, MAT["titanium"]),
]):
    prim_cyl("Respirator_Ring_%d" % (k + 1), resp + resp_n * (0.010 + k * 0.020),
             rad, dep, mk, vertices=36, direction=resp_n)
for i in range(8):
    a = i * math.pi / 4
    q = resp_n.to_track_quat("Z", "Y")
    t = q @ Vector((math.cos(a), math.sin(a), 0))
    prim_cube("Respirator_Vane_%02d" % i, resp + t * 0.062 + resp_n * 0.078,
              (0.075, 0.014, 0.012), MAT["steel"],
              rot=t.to_track_quat("X", "Z").to_euler())
prim_cyl("Respirator_Core", resp + resp_n * 0.090, 0.040, 0.018,
         MAT["steel"], vertices=24, direction=resp_n)

# 顶部传感器舱
sensor, sensor_n = surf(0.0, 0.945, PLATE_OFFSET + 0.030)
prim_cube("Sensor_Housing", sensor, (0.16, 0.13, 0.085), MAT["steel"], bevel=0.012)
prim_cyl("Sensor_Lens", sensor + sensor_n * 0.052 + Vector((0, -0.03, 0.04)),
         0.040, 0.022, MAT["visor"], vertices=24, direction=Vector((0, -0.45, 0.89)))
prim_cyl("Sensor_LED", sensor + sensor_n * 0.052 + Vector((0, 0.045, 0.04)),
         0.014, 0.012, MAT["led_amber"], vertices=16, direction=Vector((0, 0.35, 0.94)))

# 侧面信号天线
for sgn, tag in ((1, "L"), (-1, "R")):
    p, _ = surf(sgn * 1.72, 0.60, PLATE_OFFSET + 0.040)
    prim_cyl("Antenna_Base_%s" % tag, p, 0.035, 0.045, MAT["steel"], vertices=16)
    p2 = p + Vector((sgn * 0.10, 0.02, 0.16))
    d = p2 - p
    prim_cyl("Antenna_Rod_%s" % tag, (p + p2) * 0.5, 0.012, d.length,
             MAT["brushed"], vertices=12, direction=d)
    prim_sphere("Antenna_Tip_%s" % tag, p2, 0.022, MAT["led_amber"], 12, 8)

# 侧面走线：沿表面走向的曲线
def cable(name, points, radius, mat):
    cu = bpy.data.curves.new(name + "_curve", "CURVE")
    cu.dimensions = "3D"
    cu.resolution_u = 16
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(points) - 1)
    for bp, pos in zip(sp.bezier_points, points):
        bp.co = pos
        bp.handle_left_type = "AUTO"
        bp.handle_right_type = "AUTO"
    cu.bevel_depth = radius
    cu.bevel_resolution = 3
    o = bpy.data.objects.new(name, cu)
    helmet_col.objects.link(o)
    o.data.materials.append(mat)
    return o

for sgn, tag in ((1, "L"), (-1, "R")):
    pts = []
    for uu, vv in [(sgn * 0.80, 0.56), (sgn * 1.20, 0.58), (sgn * 1.58, 0.52),
                   (sgn * 1.92, 0.42), (sgn * 2.30, 0.44), (sgn * 2.62, 0.56)]:
        pp, _ = surf(uu, vv, PLATE_OFFSET + 0.030)
        pts.append(pp)
    cable("Cable_Upper_%s" % tag, pts, 0.014, MAT["rubber"])
    pts2 = []
    for uu, vv in [(sgn * 0.86, 0.50), (sgn * 1.25, 0.52), (sgn * 1.62, 0.46),
                   (sgn * 1.98, 0.36), (sgn * 2.34, 0.38)]:
        pp, _ = surf(uu, vv, PLATE_OFFSET + 0.036)
        pts2.append(pp)
    cable("Cable_Upper_B_%s" % tag, pts2, 0.009, MAT["brushed"])

# ---------------------------------------------------------------------------
# 7. 摄影棚背景（渐变）与地台
# ---------------------------------------------------------------------------
bg_mat = bpy.data.materials.new("M_Studio_Gradient")
bg_mat.use_nodes = True
nt = bg_mat.node_tree
nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputMaterial")
emit = nt.nodes.new("ShaderNodeEmission")
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements.remove(ramp.color_ramp.elements[1])
e0 = ramp.color_ramp.elements[0]
e0.position = 0.0
e0.color = (0.010, 0.011, 0.015, 1)
e1 = ramp.color_ramp.elements.new(0.52)
e1.color = (0.052, 0.056, 0.067, 1)
e2 = ramp.color_ramp.elements.new(1.0)
e2.color = (0.016, 0.018, 0.024, 1)
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
mapr = nt.nodes.new("ShaderNodeMapRange")
mapr.inputs["From Min"].default_value = -18.0
mapr.inputs["From Max"].default_value = 18.0
geo = nt.nodes.new("ShaderNodeNewGeometry")
nt.links.new(geo.outputs["Position"], sep.inputs["Vector"])
nt.links.new(sep.outputs["Z"], mapr.inputs["Value"])
nt.links.new(mapr.outputs["Result"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], emit.inputs["Color"])
nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=40)
bg = bpy.context.object
bg.name = "Studio_Backdrop_Gradient"
link_studio(bg)
bg.data.materials.append(bg_mat)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.flip_normals()
bpy.ops.object.mode_set(mode="OBJECT")

# ---------------------------------------------------------------------------
# 8. 三点工作室布光
# ---------------------------------------------------------------------------
def area_light(name, loc, power, color, size, target=(0, 0, 0)):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = power
    data.color = color
    data.shape = "RECTANGLE"
    data.size = size[0]
    data.size_y = size[1]
    obj = bpy.data.objects.new(name, data)
    studio_col.objects.link(obj)
    obj.location = loc
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return obj

area_light("Light_Key_LargeSoftbox", (-3.4, -4.6, 4.2), 660, (1.0, 0.94, 0.87), (4.0, 4.0))
area_light("Light_Fill_Cool", (4.2, -2.2, 1.6), 340, (0.60, 0.76, 1.0), (3.0, 4.0))
area_light("Light_Rim_Back", (1.0, 4.2, 3.6), 950, (0.82, 0.90, 1.0), (3.0, 2.0))
area_light("Light_Top_Kicker", (0.0, 0.6, 5.0), 150, (1.0, 1.0, 1.0), (2.4, 2.4))
area_light("Light_Amber_Accent", (-2.4, -1.2, -0.4), 110, (1.0, 0.52, 0.18), (1.4, 1.0))

# ---------------------------------------------------------------------------
# 9. 相机：三分之四视角
# ---------------------------------------------------------------------------
cam_data = bpy.data.cameras.new("Camera_Hero_ThreeQuarter")
cam = bpy.data.objects.new("Camera_Hero_ThreeQuarter", cam_data)
studio_col.objects.link(cam)
cam.location = (3.55, -5.35, 1.30)
target = Vector((0.0, 0.0, 0.02))
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
cam_data.lens = 55
cam_data.dof.use_dof = False
bpy.context.scene.camera = cam

# ---------------------------------------------------------------------------
# 10. 渲染设置（8K 主视觉），保存源文件
# ---------------------------------------------------------------------------
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 64
scene.cycles.use_denoising = True
scene.render.resolution_x = 7680
scene.render.resolution_y = 4320
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.film_transparent = False
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass

# 源文件的默认视角设为相机视角，打开即可看到成品构图
for area in bpy.context.screen.areas:
    if area.type == "VIEW_3D":
        area.spaces.active.region_3d.view_perspective = "CAMERA"

blend_path = os.path.join(OUT, "tactical_mech_helmet.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)

# 统计
mesh_objs = [o for o in helmet_col.objects if o.type == "MESH"]
tri = 0
poly = 0
for o in mesh_objs:
    poly += len(o.data.polygons)
    tri += sum(len(p.vertices) - 2 for p in o.data.polygons)
print("[build_helmet] 保存:", blend_path)
print("[build_helmet] 头盔对象: %d | 网格对象: %d | 多边形: %d | 三角面: %d | 铆钉: %d"
      % (len(helmet_col.objects), len(mesh_objs), poly, tri, rivet_count))
