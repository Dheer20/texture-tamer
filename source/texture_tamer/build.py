# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dheer
"""Build the Principled BSDF node tree from a list of (file, map type).

Only Blender's own shader nodes are used, so the result renders the same
in EEVEE and Cycles and keeps working if the add-on is removed.
"""

import math
import os

import bpy
from mathutils import Euler, Vector

P = "PBRQA "  # prefix for node names the panel looks up later

DATA_TYPES = {"AO", "ROUGHNESS", "GLOSS", "METALLIC", "SPECULAR", "NORMAL_GL",
              "NORMAL_DX", "HEIGHT", "BUMP", "OPACITY", "ARM"}

GRID_BLUE = (0.06, 0.22, 0.65, 1.0)
GRID_WHITE = (0.9, 0.9, 0.9, 1.0)


def _out(node, name, kind=None):
    """Output socket by name (and type, for the Mix node's several 'Result')."""
    for s in node.outputs:
        if s.name == name and (kind is None or s.type == kind) and s.enabled:
            return s
    return node.outputs[name]


def _in(node, name, kind=None):
    for s in node.inputs:
        if s.name == name and (kind is None or s.type == kind) and s.enabled:
            return s
    return node.inputs[name]


def load_image(path, is_data):
    img = bpy.data.images.load(path, check_existing=True)
    if is_data:
        img.colorspace_settings.is_data = True
    else:
        img.colorspace_settings.is_data = False
        if not img.is_float:
            # 8/16-bit colour files are sRGB; float files (EXR) keep
            # Blender's own linear default.
            img.colorspace_settings.name = "sRGB"
    return img


def image_aspect(img):
    """height / width of an image (1.0 if unknown)."""
    try:
        w, h = img.size[0], img.size[1]
        if w and h:
            return h / w
    except Exception:
        pass
    return 1.0


def tile_height(s):
    """Real height of one tile: follows the texture's shape unless unlinked."""
    if s.size_linked:
        return s.tile_size * (s.aspect or 1.0)
    return s.tile_height


def measure_uv_metres(obj):
    """Metres covered by one UV unit on this object (None if no UVs).

    Compares the object's real surface area (with its scale) to the area its
    faces take in the UV map: sqrt(world area / UV area).
    """
    if obj is None or obj.type != "MESH" or not obj.data.uv_layers:
        return None
    me = obj.data
    uv = me.uv_layers.active.data
    mw = obj.matrix_world
    co = [mw @ v.co for v in me.vertices]
    area3d = areauv = 0.0
    for poly in me.polygons:
        li = list(poly.loop_indices)
        if len(li) < 3:
            continue
        v0 = co[me.loops[li[0]].vertex_index]
        u0 = uv[li[0]].uv
        for a, b in zip(li[1:-1], li[2:]):
            va = co[me.loops[a].vertex_index]
            vb = co[me.loops[b].vertex_index]
            area3d += (va - v0).cross(vb - v0).length * 0.5
            ua, ub = uv[a].uv, uv[b].uv
            areauv += abs((ua.x - u0.x) * (ub.y - u0.y)
                          - (ub.x - u0.x) * (ua.y - u0.y)) * 0.5
    if area3d <= 0 or areauv <= 1e-12:
        return None
    return math.sqrt(area3d / areauv)


def _tex(nodes, name, label, img, x, y, box):
    n = nodes.new("ShaderNodeTexImage")
    n.name, n.label = P + name, label
    n.image = img
    n.location = (x, y)
    if box:
        n.projection = "BOX"
        n.projection_blend = 0.2
    return n


def _coords_socket(nodes, s):
    """Where texture positions come from, for the chosen projection."""
    if s.projection == "WORLD":
        geo = nodes.new("ShaderNodeNewGeometry")
        geo.name, geo.label, geo.location = P + "World Position", "World Position", (-2100, 0)
        return geo.outputs["Position"]
    coord = nodes.new("ShaderNodeTexCoord")
    coord.name, coord.location = P + "Coords", (-2100, 0)
    return coord.outputs["Object" if s.projection == "BOX" else "UV"]


def _random_chains(nodes, links, s, mapping):
    """Per-object random shift / quarter-turn from Object Info > Random."""
    if not (s.random_offset or s.random_turn):
        return
    info = nodes.new("ShaderNodeObjectInfo")
    info.name, info.label, info.location = P + "Object Info", "Random per object", (-2100, -350)
    rnd = info.outputs["Random"]
    link = links.new
    if s.random_turn:
        m4 = nodes.new("ShaderNodeMath")
        m4.operation, m4.name, m4.location = "MULTIPLY", P + "Rand Turn x4", (-1900, -300)
        m4.inputs[1].default_value = 4.0
        fl = nodes.new("ShaderNodeMath")
        fl.operation, fl.name, fl.location = "FLOOR", P + "Rand Turn Floor", (-1750, -300)
        q = nodes.new("ShaderNodeMath")
        q.operation, q.name, q.location = "MULTIPLY", P + "Rand Turn 90", (-1600, -300)
        q.inputs[1].default_value = math.pi / 2
        add = nodes.new("ShaderNodeMath")
        add.operation, add.name, add.location = "ADD", P + "Rand Rot Add", (-1450, -300)
        comb = nodes.new("ShaderNodeCombineXYZ")
        comb.name, comb.location = P + "Rand Rot XYZ", (-1300, -300)
        link(rnd, m4.inputs[0])
        link(m4.outputs[0], fl.inputs[0])
        link(fl.outputs[0], q.inputs[0])
        link(q.outputs[0], add.inputs[0])
        link(add.outputs[0], comb.inputs["Z"])
        link(comb.outputs[0], mapping.inputs["Rotation"])
    if s.random_offset:
        my = nodes.new("ShaderNodeMath")
        my.operation, my.name, my.location = "MULTIPLY", P + "Rand Off Mix", (-1900, -480)
        my.inputs[1].default_value = 7.31
        fr = nodes.new("ShaderNodeMath")
        fr.operation, fr.name, fr.location = "FRACT", P + "Rand Off Fract", (-1750, -480)
        comb = nodes.new("ShaderNodeCombineXYZ")
        comb.name, comb.location = P + "Rand Off XYZ", (-1600, -480)
        add = nodes.new("ShaderNodeVectorMath")
        add.operation, add.name, add.location = "ADD", P + "Rand Loc Add", (-1450, -480)
        link(rnd, comb.inputs["X"])
        link(rnd, my.inputs[0])
        link(my.outputs[0], fr.inputs[0])
        link(fr.outputs[0], comb.inputs["Y"])
        link(comb.outputs[0], add.inputs[0])
        link(add.outputs[0], mapping.inputs["Location"])


def slot_of(map_type):
    """Normal GL/DX share one slot; everything else is its own slot."""
    return "NORMAL" if map_type in ("NORMAL_GL", "NORMAL_DX") else map_type


def chosen_maps(s):
    """{slot: (index, item)} actually used: the first ticked, existing file of each
    slot, in list order. The panel shows exactly this, whatever the layout."""
    chosen = {}
    for i, it in enumerate(s.maps):
        if (it.enabled and it.map_type != "IGNORE" and it.filepath
                and os.path.isfile(it.filepath)):
            chosen.setdefault(slot_of(it.map_type), (i, it))
    return chosen


def build(mat):
    """(Re)build mat's node tree from mat.pbrqa.maps and its settings."""
    s = mat.pbrqa
    chosen = {k: v[1] for k, v in chosen_maps(s).items()}

    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()
    link = links.new

    out = nodes.new("ShaderNodeOutputMaterial")
    out.name, out.location = P + "Output", (500, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.name, bsdf.location = P + "BSDF", (100, 0)
    link(bsdf.outputs["BSDF"], out.inputs["Surface"])

    box = s.projection in ("BOX", "WORLD")
    coords = _coords_socket(nodes, s)
    mapping = nodes.new("ShaderNodeMapping")
    mapping.name, mapping.location = P + "Mapping", (-1500, 0)
    link(coords, mapping.inputs["Vector"])
    _random_chains(nodes, links, s, mapping)
    vec = mapping.outputs["Vector"]

    y = 400
    tex = {}
    for slot in ("BASE_COLOR", "AO", "ARM", "ROUGHNESS", "GLOSS", "METALLIC",
                 "SPECULAR", "NORMAL", "BUMP", "HEIGHT", "EMISSION", "OPACITY"):
        it = chosen.get(slot)
        if not it:
            continue
        if slot == "HEIGHT" and s.displacement_mode == "OFF":
            continue  # height map unused while Displacement is Off
        t = it.map_type
        img = load_image(it.filepath, t in DATA_TYPES)
        node = _tex(nodes, slot, it.label_for_node(), img, -1200, y, box)
        link(vec, node.inputs["Vector"])
        tex[slot] = node
        y -= 290

    # Remember the shape of the texture so tile size keeps it unstretched.
    first = tex.get("BASE_COLOR") or next(iter(tex.values()), None)
    s.aspect = image_aspect(first.image) if first else 1.0

    arm = None
    if "ARM" in tex:
        arm = nodes.new("ShaderNodeSeparateColor")
        arm.name, arm.label = P + "ARM Split", "Split ARM (R=AO G=Rough B=Metal)"
        arm.location = (-850, tex["ARM"].location.y)
        link(tex["ARM"].outputs["Color"], arm.inputs["Color"])

    # --- Base colour, AO multiply, variation tint multiply ---
    color = tex["BASE_COLOR"].outputs["Color"] if "BASE_COLOR" in tex else None
    ao_src = (tex["AO"].outputs["Color"] if "AO" in tex
              else (arm.outputs["Red"] if arm else None))
    if color is not None and ao_src is not None:
        mix = nodes.new("ShaderNodeMix")
        mix.name, mix.label = P + "AO Mix", "AO Multiply"
        mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
        mix.location = (-500, 450)
        link(color, _in(mix, "A", "RGBA"))
        link(ao_src, _in(mix, "B", "RGBA"))
        color = _out(mix, "Result", "RGBA")
    if (color is not None and s.tint_enabled and s.tint_path
            and os.path.isfile(s.tint_path)):
        tmap = nodes.new("ShaderNodeMapping")
        tmap.name, tmap.location = P + "Tint Mapping", (-1500, 700)
        link(coords, tmap.inputs["Vector"])
        timg = load_image(s.tint_path, False)
        tnode = _tex(nodes, "Tint Image", "Variation / Tint", timg, -1200, 800, box)
        link(tmap.outputs["Vector"], tnode.inputs["Vector"])
        mix = nodes.new("ShaderNodeMix")
        mix.name, mix.label = P + "Tint Mix", "Variation Multiply"
        mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
        mix.location = (-300, 500)
        link(color, _in(mix, "A", "RGBA"))
        link(tnode.outputs["Color"], _in(mix, "B", "RGBA"))
        color = _out(mix, "Result", "RGBA")

    # --- Check Size grid: Blender's Checker texture over the colour ---
    if s.check_grid != "OFF":
        chk = nodes.new("ShaderNodeTexChecker")
        chk.name, chk.label, chk.location = P + "Check Grid", "Check Size grid", (-500, 750)
        chk.inputs["Color1"].default_value = GRID_BLUE
        chk.inputs["Color2"].default_value = GRID_WHITE
        chk.inputs["Scale"].default_value = 1.0  # one square per unit
        if s.check_grid == "TILES":
            link(vec, chk.inputs["Vector"])  # mapped space: 1 unit = 1 tile
        elif s.projection == "UV":
            sc = nodes.new("ShaderNodeVectorMath")
            sc.operation, sc.name, sc.location = "SCALE", P + "Grid UV Metres", (-800, 750)
            link(coords, sc.inputs[0])
            link(sc.outputs["Vector"], chk.inputs["Vector"])
        else:
            link(coords, chk.inputs["Vector"])  # object / world space is metres
        gmix = nodes.new("ShaderNodeMix")
        gmix.name, gmix.label = P + "Grid Mix", "Check Size overlay (switch off to render)"
        gmix.data_type, gmix.blend_type = "RGBA", "MIX"
        gmix.location = (-250, 750)
        _in(gmix, "Factor", "VALUE").default_value = 0.7
        if color is not None:
            link(color, _in(gmix, "A", "RGBA"))
        link(chk.outputs["Color"], _in(gmix, "B", "RGBA"))
        color = _out(gmix, "Result", "RGBA")
    if color is not None:
        link(color, bsdf.inputs["Base Color"])

    # --- Roughness / gloss / metallic / specular ---
    if "ROUGHNESS" in tex:
        link(tex["ROUGHNESS"].outputs["Color"], bsdf.inputs["Roughness"])
    elif "GLOSS" in tex:
        inv = nodes.new("ShaderNodeInvert")
        inv.name, inv.label = P + "Gloss Invert", "Gloss to Roughness"
        inv.location = (-850, tex["GLOSS"].location.y)
        link(tex["GLOSS"].outputs["Color"], inv.inputs["Color"])
        link(inv.outputs["Color"], bsdf.inputs["Roughness"])
    elif arm:
        link(arm.outputs["Green"], bsdf.inputs["Roughness"])
    if "METALLIC" in tex:
        link(tex["METALLIC"].outputs["Color"], bsdf.inputs["Metallic"])
    elif arm:
        link(arm.outputs["Blue"], bsdf.inputs["Metallic"])
    if "SPECULAR" in tex:
        link(tex["SPECULAR"].outputs["Color"], bsdf.inputs["Specular IOR Level"])

    # --- Normal (with DirectX green flip) and bump ---
    normal = None
    if "NORMAL" in tex:
        ncol = tex["NORMAL"].outputs["Color"]
        if chosen["NORMAL"].map_type == "NORMAL_DX":
            sep = nodes.new("ShaderNodeSeparateColor")
            sep.name, sep.label = P + "DX Split", "DirectX: flip green"
            sep.location = (-900, tex["NORMAL"].location.y)
            flip = nodes.new("ShaderNodeMath")
            flip.name, flip.operation = P + "DX Flip", "SUBTRACT"
            flip.inputs[0].default_value = 1.0
            flip.location = (-720, tex["NORMAL"].location.y - 60)
            comb = nodes.new("ShaderNodeCombineColor")
            comb.name, comb.location = P + "DX Combine", (-540, tex["NORMAL"].location.y)
            link(ncol, sep.inputs["Color"])
            link(sep.outputs["Red"], comb.inputs["Red"])
            link(sep.outputs["Green"], flip.inputs[1])
            link(flip.outputs["Value"], comb.inputs["Green"])
            link(sep.outputs["Blue"], comb.inputs["Blue"])
            ncol = comb.outputs["Color"]
        nmap = nodes.new("ShaderNodeNormalMap")
        nmap.name, nmap.location = P + "Normal Map", (-300, tex["NORMAL"].location.y)
        link(ncol, nmap.inputs["Color"])
        normal = nmap.outputs["Normal"]
    if "BUMP" in tex:
        bump = nodes.new("ShaderNodeBump")
        bump.name, bump.location = P + "Bump", (-120, tex["BUMP"].location.y)
        link(tex["BUMP"].outputs["Color"], bump.inputs["Height"])
        if normal is not None:
            link(normal, bump.inputs["Normal"])
        normal = bump.outputs["Normal"]
    if normal is not None:
        link(normal, bsdf.inputs["Normal"])

    # --- Height: Off (default), Bump only, or Real displacement plus bump
    # (Blender's own material setting "Displacement and Bump") ---
    if "HEIGHT" in tex:
        disp = nodes.new("ShaderNodeDisplacement")
        disp.name, disp.location = P + "Displacement", (100, -700)
        link(tex["HEIGHT"].outputs["Color"], disp.inputs["Height"])
        link(disp.outputs["Displacement"], out.inputs["Displacement"])
        mat.displacement_method = "BOTH" if s.displacement_mode == "REAL" else "BUMP"
    else:
        mat.displacement_method = "BUMP"

    # --- Emission and opacity ---
    if "EMISSION" in tex:
        link(tex["EMISSION"].outputs["Color"], bsdf.inputs["Emission Color"])
    if "OPACITY" in tex:
        link(tex["OPACITY"].outputs["Color"], bsdf.inputs["Alpha"])

    s.has_height = "HEIGHT" in chosen
    s.has_normal = "NORMAL" in tex
    s.has_bump = "BUMP" in tex
    s.has_emission = "EMISSION" in tex
    s.has_ao = ao_src is not None and "BASE_COLOR" in tex
    s.has_tint = (P + "Tint Mix") in nodes
    _solo(mat, nodes, links, vec, box, out)
    apply_values(mat)


def _solo(mat, nodes, links, vec, box, out):
    """'Show this map only': the chosen image straight onto the object,
    like Node Wrangler's node preview. Everything else stays built."""
    s = mat.pbrqa
    if not 0 <= s.solo_index < len(s.maps):
        return
    it = s.maps[s.solo_index]
    if not it.filepath or not os.path.isfile(it.filepath):
        return
    img = load_image(it.filepath, it.map_type in DATA_TYPES)
    node = _tex(nodes, "Solo Image", "Showing only: " + os.path.basename(it.filepath),
                img, -200, 1100, box)
    links.new(vec, node.inputs["Vector"])
    em = nodes.new("ShaderNodeEmission")
    em.name, em.label, em.location = P + "Solo Emission", "Show one map only", (200, 1100)
    links.new(node.outputs["Color"], em.inputs["Color"])
    links.new(em.outputs["Emission"], out.inputs["Surface"])
    for l in list(out.inputs["Displacement"].links):
        links.remove(l)


def placement(s):
    """Mapping scale, location and Z rotation for the panel's values.

    Offset is in metres along the surface (before turning), so the arrows
    slide the texture sideways / up even when it is rotated.
    """
    w = max(s.tile_size, 1e-6)
    h = max(tile_height(s), 1e-6)
    if s.projection == "UV":
        u = s.uv_metres or 1.0
        scale = Vector((u / w, u / h, 1.0))
        off = Vector((s.offset_x / w, s.offset_y / h, 0.0))
    else:  # Box / World: object or world metres
        scale = Vector((1 / w, 1 / h, 1 / h))
        # Walls use X/Z, floors X/Y: "up" goes to both Y and Z.
        off = Vector((s.offset_x / w, s.offset_y / h, s.offset_y / h))
    rot = s.rotation
    loc = -(Euler((0.0, 0.0, rot)).to_matrix() @ off)
    return scale, loc, rot


def apply_values(mat):
    """Push the panel's slider values into the existing nodes (fast, no rebuild)."""
    s = mat.pbrqa
    nodes = mat.node_tree.nodes if mat.node_tree else None
    if not nodes:
        return
    g = nodes.get
    m = g(P + "Mapping")
    if m:
        scale, loc, rot = placement(s)
        m.inputs["Scale"].default_value = scale
        rb = g(P + "Rand Rot Add")
        if rb:
            rb.inputs[1].default_value = rot
        else:
            m.inputs["Rotation"].default_value = (0.0, 0.0, rot)
        lb = g(P + "Rand Loc Add")
        if lb:
            lb.inputs[1].default_value = loc
        else:
            m.inputs["Location"].default_value = loc
    tm = g(P + "Tint Mapping")
    if tm:
        tw = max(s.tint_size, 1e-6)
        if s.projection == "UV":
            u = s.uv_metres or 1.0
            tm.inputs["Scale"].default_value = (u / tw, u / tw, 1.0)
        else:
            tm.inputs["Scale"].default_value = (1 / tw,) * 3
    gu = g(P + "Grid UV Metres")
    if gu:
        gu.inputs["Scale"].default_value = s.uv_metres or 1.0
    n = g(P + "Normal Map")
    if n:
        n.inputs["Strength"].default_value = s.normal_strength
    b = g(P + "Bump")
    if b:
        b.inputs["Strength"].default_value = s.bump_strength
    d = g(P + "Displacement")
    if d:
        d.inputs["Scale"].default_value = s.displacement_height
        d.inputs["Midlevel"].default_value = s.displacement_midlevel
    bsdf = g(P + "BSDF")
    if bsdf:
        bsdf.inputs["Emission Strength"].default_value = (
            s.emission_strength if s.has_emission else 0.0)
    a = g(P + "AO Mix")
    if a:
        _in(a, "Factor", "VALUE").default_value = s.ao_strength
    t = g(P + "Tint Mix")
    if t:
        _in(t, "Factor", "VALUE").default_value = s.tint_strength
