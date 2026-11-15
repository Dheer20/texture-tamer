# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dheer
"""Guess which PBR map each image file is, from its file name only.

No bpy import here, so this file can be tested with plain Python.
The splitting rule is the same idea as Node Wrangler's
"Principled Texture Setup" (split on separators and CamelCase), with a
wider word list and with the map word searched from the END of the name,
so "metal_plate_diff_2k" is base colour, not metallic.
"""

import os
import re

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".exr", ".tga",
              ".bmp", ".webp"}

# (identifier, label, description) - used for the dropdown in the UI.
MAP_TYPES = [
    ("BASE_COLOR", "Base Color", "Colour / albedo / diffuse map (sRGB)"),
    ("AO", "AO", "Ambient occlusion: contact shadows, multiplied over the colour"),
    ("ROUGHNESS", "Roughness", "White = rough, black = shiny"),
    ("GLOSS", "Gloss", "White = shiny; inverted to roughness"),
    ("METALLIC", "Metallic", "White = metal, black = non-metal"),
    ("SPECULAR", "Specular", "Specular level map"),
    ("NORMAL_GL", "Normal GL", "Normal map, OpenGL / Blender form (Y+)"),
    ("NORMAL_DX", "Normal DX", "Normal map, DirectX form (Y-); green is flipped"),
    ("HEIGHT", "Height", "Height / displacement map (see Surface > Displacement)"),
    ("BUMP", "Bump", "Bump map; bump only, no displacement"),
    ("EMISSION", "Emission", "Glow colour map (sRGB)"),
    ("OPACITY", "Opacity", "White = solid, black = see-through"),
    ("ARM", "ARM (packed)",
     "Packed ARM/ORM map: red = AO, green = roughness, blue = metallic"),
    ("IGNORE", "Ignore", "Do not use this file"),
]
MAP_IDS = [m[0] for m in MAP_TYPES]
MAP_LABEL = {m[0]: m[1] for m in MAP_TYPES}

# Words that name a map. Lower case. Collected from Node Wrangler's
# defaults plus the names used by ambientCG, Poly Haven, Poliigon,
# FreePBR, Quixel/Megascans and Substance exports (see RESEARCH.md).
WORDS = {
    "BASE_COLOR": {"basecolor", "basecolour", "base", "color", "colour", "col",
                   "albedo", "alb", "diffuse", "diff", "dif", "diffuseoriginal"},
    "AO": {"ao", "ambientocclusion", "occlusion", "occ", "ambient", "mixedao"},
    "ROUGHNESS": {"roughness", "rough", "rgh", "rough"},
    "GLOSS": {"gloss", "glossy", "glossiness", "smoothness", "smooth"},
    "METALLIC": {"metallic", "metalness", "metal", "mtl", "metalic"},
    "SPECULAR": {"specular", "spec", "spc", "specularity", "refl",
                 "reflection"},
    "NORMAL": {"normal", "normals", "nor", "nrm", "nrml", "norm", "nmap",
               "normalgl", "normaldx", "normalmap"},
    "HEIGHT": {"height", "heightmap", "displacement", "displace", "disp",
               "dsp", "depth"},
    "BUMP": {"bump", "bmp", "bumpmap"},
    "EMISSION": {"emission", "emissive", "emit", "glow", "illum",
                 "illumination", "selfillum", "luminance"},
    "OPACITY": {"opacity", "alpha", "transparency", "transparent", "cutout"},
    "ARM": {"arm", "orm", "aorm", "occlusionroughnessmetallic"},
}
# Words that mean "this is not a map we use" (previews, masks, etc.).
SKIP_WORDS = {"preview", "thumb", "thumbnail", "sphere", "render", "cube",
              "cavity", "mask", "id", "translucency", "fuzz", "sss",
              "subsurface", "curvature", "edge", "edges", "wet",
              "screenshot", "sample", "swatch"}
DX_WORDS = {"dx", "directx", "direct", "normaldx", "d3d"}
GL_WORDS = {"gl", "ogl", "opengl", "open", "normalgl"}
# Side words of a normal name ("Normal_OpenGL" splits into normal/open/gl).
_NORMAL_SIDE = (DX_WORDS | GL_WORDS | {"x"}) - {"normaldx", "normalgl"}
# Words that are never the map word (sizes, versions, junk).
NOISE = {"k", "px", "copy", "final", "new", "img", "image", "tex", "texture",
         "textures", "map", "maps", "v", "ver", "version", "lod", "var",
         "seamless", "tileable", "png", "jpg"}

_FALLBACK = sorted(
    ((w, t) for t, ws in WORDS.items() for w in ws if len(w) >= 4),
    key=lambda p: -len(p[0]))


def split_words(filename):
    """'WallTexture_NormalGL_2K (1).png' -> ['wall', 'texture', 'normal', 'gl', 'k']"""
    stem = os.path.splitext(os.path.basename(filename))[0]
    stem = re.sub(r"([a-z])([A-Z])", r"\1 \2", stem)      # CamelCase
    stem = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", stem)  # NRMMap -> NRM Map
    stem = re.sub(r"\d+", " ", stem)                       # drop numbers
    words = re.split(r"[^A-Za-z]+", stem)
    return [w.lower() for w in words if w]


def _type_of_word(word):
    if word in WORDS["ARM"]:
        return "ARM"
    for t in ("NORMAL", "BASE_COLOR", "ROUGHNESS", "GLOSS", "METALLIC", "AO",
              "HEIGHT", "BUMP", "EMISSION", "OPACITY", "SPECULAR"):
        if word in WORDS[t]:
            return t
    return None


def classify(filename):
    """Return (map_type, set_key).

    map_type is one of MAP_IDS. set_key is the part of the name before the
    map word (used to tell two texture sets in one folder apart).
    """
    words = split_words(filename)
    found, index = None, len(words)
    # Spelled-out packed maps: "OcclusionRoughnessMetallic", "AO_Rough_Metal".
    for i in range(len(words) - 2):
        if {_type_of_word(w) for w in words[i:i + 3]} == {"AO", "ROUGHNESS", "METALLIC"}:
            key = " ".join(w for w in words[:i] if w not in NOISE)
            return "ARM", key
    # Search from the end: the map word is nearly always the last real word.
    for i in range(len(words) - 1, -1, -1):
        w = words[i]
        if w in NOISE or w in _NORMAL_SIDE:
            continue
        if w in SKIP_WORDS:
            found, index = "IGNORE", i
            break
        t = _type_of_word(w)
        if t:
            found, index = t, i
            # "ambient occlusion", "base color": step over the first word.
            if i > 0 and words[i - 1] in ("ambient", "base"):
                index = i - 1
            break
    if found is None:
        # Glued names such as "brickwalldiffuse": look for a long map word
        # at the end of the whole name.
        glued = "".join(w for w in words if w not in NOISE)
        for w, t in _FALLBACK:
            if glued.endswith(w):
                found, index = t, len(words)
                break
    if found is None:
        found = "IGNORE"
    if found == "NORMAL":
        found = "NORMAL_DX" if any(w in DX_WORDS for w in words) else "NORMAL_GL"
    key = " ".join(w for w in words[:index] if w not in NOISE)
    return found, key


def resolution_hint(filename):
    """Bigger number = higher resolution guess ('_4K' -> 4096, '2048' -> 2048)."""
    stem = os.path.splitext(os.path.basename(filename))[0].lower()
    m = re.search(r"(\d+)\s*k(?![a-z])", stem)
    if m:
        return int(m.group(1)) * 1024
    m = re.search(r"(?<!\d)(256|512|1024|2048|4096|8192|16384)(?!\d)", stem)
    return int(m.group(1)) if m else 0


_FORMAT_RANK = {".exr": 5, ".tif": 4, ".tiff": 4, ".png": 3, ".tga": 2,
                ".webp": 1, ".bmp": 1, ".jpg": 0, ".jpeg": 0}

# Which slot a type fills (both normal forms fill one slot).
SLOT = {"NORMAL_GL": "NORMAL", "NORMAL_DX": "NORMAL", "GLOSS": "ROUGHNESS"}


def detect_files(paths, prefer_key=None):
    """Classify a list of image paths and pick one file per map slot.

    Returns a list of dicts: {path, type, guess, key}. Files that lose to a
    better duplicate (other resolution, other format, DirectX when OpenGL
    exists, another set in the same folder) are set to IGNORE, but stay in
    the list so the user can switch them back.
    """
    items = []
    for p in sorted(paths, key=lambda s: os.path.basename(s).lower()):
        if os.path.splitext(p)[1].lower() not in IMAGE_EXTS:
            continue
        t, key = classify(p)
        items.append({"path": p, "type": t, "guess": t, "key": key})

    # Main set = the one the user picked, else the set with most maps.
    counts = {}
    for it in items:
        if it["type"] != "IGNORE":
            counts[it["key"]] = counts.get(it["key"], 0) + 1
    main = prefer_key if prefer_key in counts else (
        max(counts, key=counts.get) if counts else None)

    def rank(it):
        p = it["path"]
        try:
            size = os.path.getsize(p)
        except OSError:
            size = 0
        return (it["key"] == main,
                it["type"] != "NORMAL_DX",
                it["type"] != "GLOSS",
                resolution_hint(p),
                _FORMAT_RANK.get(os.path.splitext(p)[1].lower(), 0),
                size)

    by_slot = {}
    for it in items:
        if it["type"] == "IGNORE":
            continue
        by_slot.setdefault(SLOT.get(it["type"], it["type"]), []).append(it)
    for group in by_slot.values():
        group.sort(key=rank, reverse=True)
        for loser in group[1:]:
            loser["type"] = "IGNORE"
    return items


def set_name(items):
    """A readable material name from the chosen files."""
    keys = [it["key"] for it in items if it["type"] != "IGNORE" and it["key"]]
    if keys:
        best = max(set(keys), key=keys.count)
        return "_".join(best.split())
    return "PBR_Material"


# ------------------------------------------------------------ set extras
VARIATION_WORDS = {"tint", "macro", "variation", "variance"}


def find_info_size(folder):
    """Real-world tile size stored in a JSON file next to the maps.

    Looks for a key like "tile_size_m" ([width, height] or one number, in
    metres) in any small .json file in the folder. Returns (w, h) or None.
    """
    import json
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return None
    for name in names:
        if not name.lower().endswith(".json"):
            continue
        path = os.path.join(folder, name)
        try:
            if os.path.getsize(path) > 256 * 1024:
                continue
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        for key in ("tile_size_m", "real_size_m", "size_m"):
            v = data.get(key)
            try:
                if isinstance(v, (int, float)) and v > 0:
                    return float(v), float(v)
                if isinstance(v, (list, tuple)) and len(v) >= 2 and v[0] > 0 and v[1] > 0:
                    return float(v[0]), float(v[1])
            except TypeError:
                continue
    return None


def find_variation_map(folder):
    """A large tint/variation image in the set's folder or a sibling folder.

    Only sibling folders named like "macro" / "variation" are searched, e.g.
    <material>/procedural/<maps> and <material>/macro/<name>_macro_tint.png.
    Returns a path or None.
    """
    def images(d):
        try:
            return [os.path.join(d, f) for f in sorted(os.listdir(d))
                    if os.path.splitext(f)[1].lower() in IMAGE_EXTS]
        except OSError:
            return []

    places = [folder]
    parent = os.path.dirname(os.path.normpath(folder))
    try:
        places += [os.path.join(parent, d) for d in sorted(os.listdir(parent))
                   if os.path.isdir(os.path.join(parent, d))
                   and os.path.normpath(os.path.join(parent, d)) != os.path.normpath(folder)
                   and set(split_words(d)) & VARIATION_WORDS]  # e.g. a "macro" folder
    except OSError:
        pass
    best = None
    for d in places:
        for p in images(d):
            words = set(split_words(p))
            if not words & VARIATION_WORDS or words & {"wet", "mask", "preview"}:
                continue
            if "tint" in words:
                return p
            best = best or p
    return best


def find_info_displacement(folder):
    """(scale_m, midlevel) from a set's JSON file, e.g.
    {"displacement": {"scale_m": 0.002, "midlevel": 0.0}}. None if absent."""
    import json
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return None
    for name in names:
        if not name.lower().endswith(".json"):
            continue
        path = os.path.join(folder, name)
        try:
            if os.path.getsize(path) > 256 * 1024:
                continue
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        d = data.get("displacement") if isinstance(data, dict) else None
        if isinstance(d, dict):
            try:
                scale = float(d.get("scale_m"))
                mid = float(d.get("midlevel", 0.5))
            except (TypeError, ValueError):
                continue
            if scale > 0 and 0.0 <= mid <= 1.0:
                return scale, mid
    return None
