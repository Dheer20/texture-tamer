"""Headless test of the installed extension in Blender.

Run (from D:/Blender/pbr_quick_apply, after installing the zip into the
isolated test profile, see tests/run_tests.sh):
  BLENDER_USER_RESOURCES=tests/_blender_user blender -b --factory-startup --python tests/test_blender.py
Prints PASS/FAIL lines and writes small renders to tests/renders/.
"""
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
REN = os.path.join(HERE, "renders")
SRC = os.environ.get("TT_TEST_SETS", "D:/Blender/backrooms_pbr")  # read only
os.makedirs(REN, exist_ok=True)

bpy.ops.preferences.addon_enable(module="bl_ext.user_default.texture_tamer")
P = "PBRQA "
results = []


def check(name, ok, extra=""):
    results.append(ok)
    print("%s  %s %s" % ("PASS" if ok else "FAIL", name, extra))


def fresh_plane():
    for o in list(bpy.data.objects):
        if o.type == "MESH":
            bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_plane_add(size=2)
    return bpy.context.active_object


def run(**kw):
    return bpy.ops.pbrqa.load_texture_set("EXEC_DEFAULT", **kw)


def linked(mat, to_node, to_socket):
    n = mat.node_tree.nodes.get(P + to_node)
    return bool(n and n.inputs[to_socket].is_linked)


def node(mat, name):
    return mat.node_tree.nodes.get(P + name)


def colour_ok(mat):
    """sRGB only for colour and emission maps, Non-Color for the rest."""
    bad = []
    for n in mat.node_tree.nodes:
        if n.bl_idname != "ShaderNodeTexImage" or not n.image:
            continue
        want_data = n.name not in (P + "BASE_COLOR", P + "EMISSION", P + "Tint Image")
        if n.image.colorspace_settings.is_data != want_data:
            bad.append(n.name)
    return not bad, bad


def files(*names):
    return [{"name": n} for n in names]


def types(mat):
    return {os.path.basename(m.filepath): m.map_type for m in mat.pbrqa.maps}


# ------------------------------------------------------------------ cases
cases = []

# A. Original carpet set, whole folder picked.
ob = fresh_plane()
run(directory=SRC + "/carpet/procedural/")
m = ob.active_material
cases.append(("orig_carpet", m))
check("A carpet: material made", m is not None and m.pbrqa.managed, m.name if m else "")
check("A carpet: base colour wired", linked(m, "BSDF", "Base Color"))
check("A carpet: AO multiplied", node(m, "AO Mix") is not None)
check("A carpet: roughness wired", linked(m, "BSDF", "Roughness"))
check("A carpet: OpenGL normal, no flip", linked(m, "BSDF", "Normal") and node(m, "DX Flip") is None)
check("A carpet: displacement Off by default (height unused)",
      m.pbrqa.displacement_mode == "OFF" and not linked(m, "Output", "Displacement")
      and node(m, "HEIGHT") is None and m.pbrqa.has_height)
check("A carpet: depth + midlevel from the set's info file",
      abs(m.pbrqa.displacement_height - 0.002058) < 1e-6 and m.pbrqa.displacement_midlevel == 0.0)
m.pbrqa.displacement_mode = "BUMP"
check("A carpet: Bump mode = height as bump only", linked(m, "Output", "Displacement")
      and m.displacement_method == "BUMP")
m.pbrqa.displacement_mode = "REAL"
check("A carpet: Real mode = displacement + bump", linked(m, "Output", "Displacement")
      and m.displacement_method == "BOTH")
check("A carpet: 16-bit height kept as float", node(m, "HEIGHT").image.is_float)
ok, bad = colour_ok(m)
check("A carpet: colour spaces", ok, bad)
check("A carpet: UV size measured (2 m plane)", abs(m.pbrqa.uv_metres - 2.0) < 1e-3,
      m.pbrqa.uv_metres)

# B. Original light panel, ONE image picked -> whole set found.
ob = fresh_plane()
run(directory=SRC + "/light_panel/procedural/", files=files("light_panel_procedural_ao.png"))
m = ob.active_material
cases.append(("orig_light_panel", m))
check("B light: emission wired", linked(m, "BSDF", "Emission Color"))
check("B light: metallic wired", linked(m, "BSDF", "Metallic"))
check("B light: 2:1 texture shape kept", abs(m.pbrqa.aspect - 0.5) < 1e-6, m.pbrqa.aspect)
m.pbrqa.emission_strength = 10.0
check("B light: emission slider", node(m, "BSDF").inputs["Emission Strength"].default_value == 10.0)
m.pbrqa.tile_size = 1.2192
sc = node(m, "Mapping").inputs["Scale"].default_value
check("B light: tile size 1.2192 m -> mapping", abs(sc[0] - 2 / 1.2192) < 1e-4
      and abs(sc[1] - 2 / 0.6096) < 1e-4, tuple(round(v, 4) for v in sc))
ok, bad = colour_ok(m)
check("B light: colour spaces", ok, bad)

# C. Original baseboard folder.
ob = fresh_plane()
run(directory=SRC + "/baseboard/procedural/")
m = ob.active_material
check("C baseboard: 5 maps used", sum(t != "IGNORE" for t in types(m).values()) == 5, types(m))
check("C baseboard: name from files", m.name.startswith("baseboard_procedural"), m.name)

# D. Messy carpet copy: DirectX normal, gloss, jpg, preview + txt junk.
ob = fresh_plane()
run(directory=DATA + "/carpet_messy/")
m = ob.active_material
cases.append(("messy_carpet", m))
t = types(m)
check("D messy: preview ignored", t.get("carpet_preview.jpg") == "IGNORE", t)
check("D messy: txt not listed", "readme.txt" not in t)
check("D messy: DirectX normal flipped", node(m, "DX Flip") is not None)
check("D messy: gloss inverted", node(m, "Gloss Invert") is not None
      and linked(m, "BSDF", "Roughness"))
check("D messy: AO multiplied", node(m, "AO Mix") is not None)
m.pbrqa.displacement_mode = "REAL"
check("D messy: height -> displacement", linked(m, "Output", "Displacement"))
ok, bad = colour_ok(m)
check("D messy: colour spaces", ok, bad)

# E. Zip with packed ARM map.
ob = fresh_plane()
run(filepath=DATA + "/lightpanel_download.zip",
    directory=DATA + "/", files=files("lightpanel_download.zip"))
m = ob.active_material
cases.append(("zip_arm_light", m))
check("E zip: unpacked", os.path.isdir(DATA + "/lightpanel_download/LightPanel_2K"))
check("E zip: ARM split", node(m, "ARM Split") is not None)
check("E zip: ARM -> AO, rough, metal", node(m, "AO Mix") is not None
      and linked(m, "BSDF", "Roughness") and linked(m, "BSDF", "Metallic"))
check("E zip: emission wired", linked(m, "BSDF", "Emission Color"))
m.pbrqa.emission_strength = 10.0
ok, bad = colour_ok(m)
check("E zip: colour spaces", ok, bad)

# F. Glued names + an unrelated mask in the folder.
ob = fresh_plane()
run(directory=DATA + "/wallpaper_glued/")
m = ob.active_material
t = types(m)
check("F glued: 4 maps found", sum(v != "IGNORE" for v in t.values()) == 4, t)
check("F glued: mask ignored", t.get("wallpaper_floor_grime_mask.png") == "IGNORE")

# G. ambientCG style, GL + DX normals and two resolutions of colour.
ob = fresh_plane()
run(directory=DATA + "/ceiling_acg/")
m = ob.active_material
t = types(m)
check("G acg: OpenGL normal chosen over DirectX",
      t["Ceiling001_2K-PNG_NormalGL.png"] == "NORMAL_GL"
      and t["Ceiling001_2K-PNG_NormalDX.png"] == "IGNORE")
check("G acg: 2K PNG colour chosen over 1K JPG",
      t["Ceiling001_2K-PNG_Color.png"] == "BASE_COLOR"
      and t["Ceiling001_1K-JPG_Color.jpg"] == "IGNORE")
# Correct a guess after applying: use the DX normal instead -> rebuilds at once.
for it in m.pbrqa.maps:
    if it.filepath.endswith("NormalGL.png"):
        it.map_type = "IGNORE"
for it in m.pbrqa.maps:
    if it.filepath.endswith("NormalDX.png"):
        it.map_type = "NORMAL_DX"
check("G acg: changing a map type rebuilds", node(m, "DX Flip") is not None)

# H. Preview-first flow (pending list), then apply.
ob = fresh_plane()
run(directory=DATA + "/carpet_messy/", apply_now=False)
pend = bpy.context.scene.pbrqa_pending
check("H pending: list filled, nothing applied", len(pend.maps) == 6 and ob.active_material is None,
      len(pend.maps))
for it in pend.maps:  # user fixes a guess before applying
    if it.filepath.endswith("NRM-DX.png"):
        it.map_type = "NORMAL_GL"
bpy.ops.pbrqa.apply_pending()
m = ob.active_material
check("H pending: applied with the correction", m is not None and node(m, "DX Flip") is None
      and linked(m, "BSDF", "Normal"))

# I. Variation / tint map, sliders, box projection, subdivision.
m.pbrqa.tint_path = DATA + "/variation/big_tint_map.png"
check("I tint: multiply node added", node(m, "Tint Mix") is not None and m.pbrqa.has_tint)
m.pbrqa.tint_size = 8.0
check("I tint: own scale", abs(node(m, "Tint Mapping").inputs["Scale"].default_value[0] - 2 / 8) < 1e-6)
m.pbrqa.displacement_mode = "REAL"
m.pbrqa.normal_strength = 0.3
m.pbrqa.displacement_height = 0.002
m.pbrqa.displacement_midlevel = 0.0
m.pbrqa.rotation = 0.5
check("I sliders reach nodes",
      abs(node(m, "Normal Map").inputs["Strength"].default_value - 0.3) < 1e-6
      and abs(node(m, "Displacement").inputs["Scale"].default_value - 0.002) < 1e-6
      and abs(node(m, "Mapping").inputs["Rotation"].default_value[2] - 0.5) < 1e-6)
m.pbrqa.projection = "BOX"
check("I box projection", node(m, "BASE_COLOR").projection == "BOX"
      and node(m, "Coords").outputs["Object"].is_linked)
bpy.ops.pbrqa.add_subdivision()
check("I subdivision added", "PBR Displacement" in ob.modifiers)
for o in list(bpy.data.objects):
    if o.type == "MESH":
        o.modifiers.clear()

# J. Drop-style call: invoke with a single file already set (what a drop does).
ob = fresh_plane()
r = bpy.ops.pbrqa.load_texture_set("INVOKE_DEFAULT", directory=DATA + "/wallpaper_glued/",
                                   files=files("wallpapernormal.png"))
check("J drop-style invoke applies directly", "FINISHED" in r and ob.active_material is not None, r)

# K. Nothing recognisable -> clean warning, nothing made.
n_before = len(bpy.data.materials)
r = run(directory=DATA + "/variation/")
check("K folder with no maps: cancelled, no material",
      "CANCELLED" in r and len(bpy.data.materials) == n_before, r)

# M. Version 1.1 placement controls.
import math
from mathutils import Vector

carpet = cases[0][1]
cs = carpet.pbrqa
check("M size from texture info: carpet 1 m", abs(cs.tile_size - 1.0) < 1e-6 and cs.info_width == 1.0)
check("M variation map found next to the set",
      cs.tint_path.endswith("carpet_macro_tint.png") and cs.tint_auto
      and abs(cs.tint_size - 8.0) < 1e-6 and node(carpet, "Tint Mix") is not None, cs.tint_path)
ext = sys.modules["bl_ext.user_default.texture_tamer"]
build = sys.modules["bl_ext.user_default.texture_tamer.build"]

# Light panel: 1.2192 x 0.6096 m from its info file, texture shape kept.
ob = fresh_plane()
run(directory=SRC + "/light_panel/procedural/")
lm = ob.active_material
ls = lm.pbrqa
check("M light: size from info, shape kept", abs(ls.tile_size - 1.2192) < 1e-6 and ls.size_linked
      and abs(build.tile_height(ls) - 0.6096) < 1e-6, (ls.tile_size, build.tile_height(ls)))
check("M light: no variation map nearby", not ls.tint_path)

# Messy carpet has no info file -> 1 m default, preset label "1 m".
ms = [mm for nn, mm in cases if nn == "messy_carpet"][0].pbrqa
check("M messy: default 1 m", abs(ms.tile_size - 1.0) < 1e-6)

# Presets menu items, unlink, height.
ob = fresh_plane()
run(directory=SRC + "/baseboard/procedural/")
m = ob.active_material
s = m.pbrqa
mp = node(m, "Mapping")
check("M baseboard: size 0.5 m from info", abs(s.tile_size - 0.5) < 1e-6)
bpy.ops.pbrqa.set_size(width=2.0, height=0.0)
check("M preset 2 m", abs(s.tile_size - 2.0) < 1e-6 and s.size_linked
      and abs(mp.inputs["Scale"].default_value[0] - 2.0 / 2.0) < 1e-6)
s.size_linked = False
check("M unlink keeps current height", abs(s.tile_height - 2.0) < 1e-6)
s.tile_height = 0.5
check("M height on its own", abs(mp.inputs["Scale"].default_value[1] - 2.0 / 0.5) < 1e-6
      and abs(mp.inputs["Scale"].default_value[0] - 1.0) < 1e-6)
s.size_linked = True

# Saved presets (Blender's own preset system), into the throw-away profile.
bpy.ops.pbrqa.set_size(width=0.8, height=0.0)
bpy.ops.pbrqa.size_preset_add(name="Hallway")
pfile = bpy.utils.preset_find("Hallway", ext.PRESET_DIR)
s.tile_size = 3.0
if pfile:
    bpy.ops.script.execute_preset(filepath=pfile, menu_idname="PBRQA_MT_size_presets")
check("M saved preset written and restored", bool(pfile) and abs(s.tile_size - 0.8) < 1e-6, pfile)

# Rotation buttons and offset that slides along the surface.
bpy.ops.pbrqa.turn(degrees=90.0)
check("M turn +90", abs(math.degrees(s.rotation) - 90.0) < 1e-4)
bpy.ops.pbrqa.turn(degrees=-90.0)
bpy.ops.pbrqa.turn(degrees=-90.0)
check("M turn wraps to 270", abs(math.degrees(s.rotation) - 270.0) < 1e-4, math.degrees(s.rotation))
s.rotation = 0.0
s.offset_x = 0.2
loc = Vector(mp.inputs["Location"].default_value)
check("M offset X", abs(loc.x + 0.2 / 0.8) < 1e-6 and abs(loc.y) < 1e-6, tuple(loc))
s.rotation = math.radians(90)
loc = Vector(mp.inputs["Location"].default_value)
check("M offset follows the turn", abs(loc.y + 0.2 / 0.8) < 1e-6 and abs(loc.x) < 1e-6, tuple(loc))

# Fit to Object (2 m plane) and the "Tiles Across" redo value.
s.tile_size = 1.44
bpy.ops.pbrqa.fit_to_object()
check("M fit: whole tiles (2 m plane, 1.44 m -> 1 tile of 2 m)", abs(s.tile_size - 2.0) < 1e-6)
bpy.ops.pbrqa.fit_to_object(tiles_across=3)
check("M fit: 3 tiles across", abs(s.tile_size - 2.0 / 3) < 1e-6)

# Reset puts the info size back.
bpy.ops.pbrqa.reset_placement()
check("M reset", abs(s.tile_size - 0.5) < 1e-6 and s.rotation == 0.0 and s.offset_x == 0.0
      and s.projection == "UV")

# Check Size grid.
s.check_grid = "TILES"
mp = node(m, "Mapping")
check("M tile grid: checker on mapped coords",
      node(m, "Check Grid") is not None and node(m, "Check Grid").inputs["Vector"].links[0].from_node == mp
      and node(m, "BSDF").inputs["Base Color"].links[0].from_node == node(m, "Grid Mix"))
s.check_grid = "METRES"
check("M 1 m grid: scaled by UV size", node(m, "Grid UV Metres") is not None
      and abs(node(m, "Grid UV Metres").inputs["Scale"].default_value - s.uv_metres) < 1e-6)
s.check_grid = "OFF"
check("M grid off: removed", node(m, "Check Grid") is None and node(m, "Grid Mix") is None)

# World projection and random per object.
s.projection = "WORLD"
check("M world projection", node(m, "World Position") is not None
      and node(m, "Mapping").inputs["Vector"].is_linked and node(m, "BASE_COLOR").projection == "BOX")
s.projection = "UV"
s.rotation = math.radians(90)
s.random_turn = True
s.random_offset = True
mp = node(m, "Mapping")
check("M random per object wired", node(m, "Object Info") is not None
      and mp.inputs["Rotation"].is_linked and mp.inputs["Location"].is_linked
      and abs(node(m, "Rand Rot Add").inputs[1].default_value - math.radians(90)) < 1e-6)
s.random_turn = s.random_offset = False
s.rotation = 0.0
check("M random off: plain values again", node(m, "Object Info") is None
      and not node(m, "Mapping").inputs["Rotation"].is_linked)

# Variation map tick.
s.tint_path = DATA + "/variation/big_tint_map.png"
s.tint_enabled = False
check("M variation ticked off", node(m, "Tint Mix") is None)
s.tint_enabled = True
check("M variation ticked on", node(m, "Tint Mix") is not None)

# Check-size render for a visual look (tile grid on the carpet, 1 tile = 0.5 m).
grid_case = m

# N. Version 1.2: map on/off, show one map, add/remove, pending on/off.
ob = fresh_plane()
run(directory=DATA + "/carpet_messy/")
m = ob.active_material
s = m.pbrqa
base = [i for i, it in enumerate(s.maps) if it.map_type == "BASE_COLOR"][0]
s.maps[base].enabled = False
check("N base colour unticked: not used", node(m, "BASE_COLOR") is None
      and not linked(m, "BSDF", "Base Color"))
s.maps[base].enabled = True
check("N ticked again: back", linked(m, "BSDF", "Base Color"))
rough = [i for i, it in enumerate(s.maps) if it.map_type == "GLOSS"][0]
bpy.ops.pbrqa.solo_map(index=rough)
check("N show one map: emission of that image on the surface",
      s.solo_index == rough and node(m, "Output").inputs["Surface"].links[0].from_node == node(m, "Solo Emission")
      and node(m, "Solo Image").image.colorspace_settings.is_data)
bpy.ops.pbrqa.solo_map(index=rough)
check("N click again: whole material back", s.solo_index == -1
      and node(m, "Output").inputs["Surface"].links[0].from_node == node(m, "BSDF") and node(m, "Solo Image") is None)
prev = [i for i, it in enumerate(s.maps) if it.filepath.endswith("carpet_preview.jpg")][0]
bpy.ops.pbrqa.solo_map(index=prev)
check("N an ignored file can be looked at too", node(m, "Solo Image") is not None)
n0 = len(s.maps)
bpy.ops.pbrqa.add_map(filepath=DATA + "/ceiling_acg/Ceiling001_2K-PNG_Metalness.png")
check("N add map: guessed + wired", len(s.maps) == n0 + 1 and s.maps[-1].map_type == "METALLIC"
      and linked(m, "BSDF", "Metallic"))
s.index = prev  # remove the row being shown: show-one-map switches off
bpy.ops.pbrqa.remove_map()
check("N remove map", len(s.maps) == n0 and s.solo_index == -1 and node(m, "Solo Image") is None)
run(directory=DATA + "/carpet_messy/", apply_now=False)
pend = bpy.context.scene.pbrqa_pending
for it in pend.maps:
    if it.map_type == "AO":
        it.enabled = False
bpy.ops.pbrqa.apply_pending()
m2 = bpy.context.active_object.active_material
check("N unticked before applying stays unticked", m2 is not m and node(m2, "AO Mix") is None
      and any(not it.enabled for it in m2.pbrqa.maps))

# O. Version 1.3: layout preferences and the By Channel actions.
prefs = bpy.context.preferences.addons["bl_ext.user_default.texture_tamer"].preferences
check("O prefs default: By Channel + Size First",
      prefs.maps_layout == "CHANNEL" and prefs.placement_layout == "SIZE_FIRST"
      and ext._maps_layout(bpy.context) == "CHANNEL")
prefs.maps_layout, prefs.placement_layout = "GRID", "HEADER"
check("O prefs switch", ext._maps_layout(bpy.context) == "GRID"
      and ext._place_layout(bpy.context) == "HEADER")
prefs.maps_layout, prefs.placement_layout = "CHANNEL", "SIZE_FIRST"

ob = fresh_plane()
run(directory=DATA + "/carpet_messy/")
m = ob.active_material
s = m.pbrqa
own = ext._channel_owner(s, "ROUGHNESS")
check("O channel owners", ext._channel_owner(s, "BASE_COLOR")[1].filepath.endswith("(1).jpg")
      and own[1].map_type == "GLOSS" and ext._channel_owner(s, "METALLIC") is None)
prev = [i for i, it in enumerate(s.maps) if it.filepath.endswith("carpet_preview.jpg")][0]
bpy.ops.pbrqa.assign_channel(channel="BASE_COLOR", index=prev)
check("O use another file for Base Color",
      s.maps[prev].map_type == "BASE_COLOR"
      and node(m, "BASE_COLOR").image.filepath.endswith("carpet_preview.jpg")
      and sum(it.map_type == "BASE_COLOR" for it in s.maps) == 1)
bpy.ops.pbrqa.assign_channel(channel="AO", index=-1)
check("O channel set to None", ext._channel_owner(s, "AO") is None and node(m, "AO Mix") is None)
bpy.ops.pbrqa.toggle_variant(index=own[0])
check("O gloss switched to roughness", s.maps[own[0]].map_type == "ROUGHNESS"
      and node(m, "Gloss Invert") is None and linked(m, "BSDF", "Roughness"))
nrm = ext._channel_owner(s, "NORMAL")[0]
bpy.ops.pbrqa.toggle_variant(index=nrm)
check("O DirectX switched to OpenGL", s.maps[nrm].map_type == "NORMAL_GL" and node(m, "DX Flip") is None)
bpy.ops.pbrqa.add_map(filepath=SRC + "/light_panel/procedural/light_panel_procedural_emission.png",
                      channel="EMISSION")
check("O add map into an empty channel", ext._channel_owner(s, "EMISSION") is not None
      and linked(m, "BSDF", "Emission Color"))
bpy.ops.pbrqa.toggle_grid()
on = s.check_grid == "TILES"
bpy.ops.pbrqa.toggle_grid()
check("O Show Tile Grid button on/off", on and s.check_grid == "OFF")
bpy.ops.pbrqa.select_map(index=2)
check("O picture-grid select", s.index == 2)

# P. 1.3.1: one rule for every layout.
ob = fresh_plane()
run(directory=DATA + "/carpet_messy/")
m = ob.active_material
s = m.pbrqa
old_base = ext._channel_owner(s, "BASE_COLOR")[0]
prev = [i for i, it in enumerate(s.maps) if it.filepath.endswith("carpet_preview.jpg")][0]
s.maps[prev].map_type = "BASE_COLOR"  # what the list layouts do
check("P list type change takes the channel over",
      s.maps[old_base].map_type == "IGNORE" and sum(it.map_type == "BASE_COLOR" for it in s.maps) == 1
      and node(m, "BASE_COLOR").image.filepath.endswith("carpet_preview.jpg"))
# Old files may hold duplicates: the channel view must show the file the build uses.
nrm = ext._channel_owner(s, "NORMAL")[0]
s.maps[old_base]["map_type"] = ext.detect.MAP_IDS.index("NORMAL_GL")  # bypass the rule
build.build(m)
used = node(m, "NORMAL").image.filepath
check("P channel view shows the file actually used",
      s.maps[ext._channel_owner(s, "NORMAL")[0]].filepath.replace("\\", "/").endswith(
          os.path.basename(used)), (used, ext._channel_owner(s, "NORMAL")[1].filepath))
s.rotation = math.radians(90)
s.projection = "WORLD"
check("P folded section names hidden changes",
      ext._hidden_summary(s) == "World, 90°" and ext._hidden_summary(s, False) == "90°",
      ext._hidden_summary(s))

# L. Material survives save + reload with its settings.
for mm in bpy.data.materials:
    if mm.pbrqa.managed:
        mm.use_fake_user = True  # objects were removed by the test
path = os.path.join(REN, "_saved_test.blend")
bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)

# ------------------------------------------------------------------ renders
def render(mat, name, engine="BLENDER_EEVEE", size=240, samples=16):
    ob = fresh_plane()
    ob.data.materials.append(mat)
    sc = bpy.context.scene
    sc.render.engine = engine
    sc.render.resolution_x = sc.render.resolution_y = size
    sc.render.resolution_percentage = 100
    if engine == "CYCLES":
        sc.cycles.samples = samples
        sc.cycles.device = "CPU"
    else:
        sc.eevee.taa_render_samples = samples
    if "TestCam" not in bpy.data.objects:
        bpy.ops.object.camera_add(location=(0, -1.25, 1.0), rotation=(0.9, 0, 0))
        bpy.context.active_object.name = "TestCam"
        bpy.ops.object.light_add(type="SUN", rotation=(0.9, 0.3, 0.6))
        bpy.context.active_object.data.energy = 3.0
    sc.camera = bpy.data.objects["TestCam"]
    sc.render.filepath = os.path.join(REN, name + ".png")
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(sc.render.filepath, check_existing=False)
    px = np.empty(len(img.pixels), dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(-1, 4)[:, :3]


bpy.context.scene.world = bpy.data.worlds.new("w") if not bpy.context.scene.world else bpy.context.scene.world
imgs = {}
for name, mat in cases:
    mat.pbrqa.tile_size = 1.0
    mat.pbrqa.tint_enabled = False  # compare the maps themselves
    imgs[name] = render(mat, "eevee_" + name)
    check("render %s not blank" % name, float(imgs[name].std()) > 0.005, round(float(imgs[name].std()), 4))
d_ok = float(np.abs(imgs["orig_carpet"] - imgs["messy_carpet"]).mean())
# Same messy set but with the DX flip and gloss invert switched off on purpose:
bad = [mm for nn, mm in cases if nn == "messy_carpet"][0].copy()
for it in bad.pbrqa.maps:
    if it.map_type == "NORMAL_DX":
        it.map_type = "NORMAL_GL"
    elif it.map_type == "GLOSS":
        it.map_type = "ROUGHNESS"
d_bad = float(np.abs(imgs["orig_carpet"] - render(bad, "eevee_messy_carpet_WRONG")).mean())
check("messy carpet looks like the original (closer than the un-fixed version)",
      d_ok < d_bad, "diff fixed %.4f vs unfixed %.4f" % (d_ok, d_bad))
cyc = render([mm for nn, mm in cases if nn == "zip_arm_light"][0], "cycles_zip_arm_light",
             engine="CYCLES", size=96, samples=16)
check("cycles render not blank", float(cyc.std()) > 0.005)
grid_case.pbrqa.check_grid = "TILES"
render(grid_case, "eevee_check_tile_grid")
grid_case.pbrqa.check_grid = "METRES"
render(grid_case, "eevee_check_1m_grid")
grid_case.pbrqa.check_grid = "OFF"
grid_case.pbrqa.random_turn = True
render(grid_case, "eevee_random_turn")

# Reload the saved file last.
bpy.ops.wm.open_mainfile(filepath=path)
mats = [mm for mm in bpy.data.materials if mm.pbrqa.managed]
check("L saved file keeps materials + settings", len(mats) >= 7
      and any(mm.pbrqa.tint_path for mm in mats), len(mats))
os.remove(path)

print("RESULT: %d/%d passed" % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
