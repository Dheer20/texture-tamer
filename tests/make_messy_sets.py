"""Make small, badly named copies of the Backrooms texture sets for testing.

Run:  blender -b --factory-startup --python tests/make_messy_sets.py
Reads D:/Blender/backrooms_pbr (read only). Writes tests/data/ only.
Each copy is shrunk to 512 px wide so the tests stay light.
Also makes the awkward forms on purpose: DirectX normal (green flipped),
gloss (roughness inverted), packed ARM (AO/rough/metal in R/G/B), a zip.
"""
import os
import shutil
import zipfile

import bpy
import numpy as np

SRC = os.environ.get("TT_TEST_SETS", "D:/Blender/backrooms_pbr")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data")
W = 512


def load(path):
    img = bpy.data.images.load(path)
    img.colorspace_settings.is_data = True  # copy raw values, no conversion
    w, h = img.size
    img.scale(W, max(1, round(W * h / w)))
    px = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    return img.size[:], px.reshape(-1, 4)


def save(size, px, path, depth="8", fmt="PNG"):
    img = bpy.data.images.new("tmp", size[0], size[1], alpha=False,
                              float_buffer=(depth == "16"), is_data=True)
    img.pixels.foreach_set(np.clip(px, 0, 1).astype(np.float32).ravel())
    s = bpy.context.scene.render.image_settings
    s.file_format = fmt
    s.color_mode = "RGB"
    if fmt == "PNG":
        s.color_depth = depth
    if fmt == "JPEG":
        s.quality = 92
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save_render(path)
    bpy.data.images.remove(img)


def src(name, kind):
    return os.path.join(SRC, name, "procedural", "%s_procedural_%s.png" % (name, kind))


vs = bpy.context.scene.view_settings
vs.view_transform, vs.look, vs.exposure, vs.gamma = "Standard", "None", 0.0, 1.0
shutil.rmtree(OUT, ignore_errors=True)

# 1) carpet: phone-camera style names, DirectX normal, gloss, JPEG, junk files.
d = os.path.join(OUT, "carpet_messy")
sz, c = load(src("carpet", "basecolor"))
save(sz, c, os.path.join(d, "IMG_2034 Carpet Diffuse (1).jpg"), fmt="JPEG")
sz, n = load(src("carpet", "normal_gl"))
n[:, 1] = 1.0 - n[:, 1]
save(sz, n, os.path.join(d, "carpet-NRM-DX.png"))
sz, r = load(src("carpet", "roughness"))
r[:, :3] = 1.0 - r[:, :3]
save(sz, r, os.path.join(d, "Carpet_GLOSS.png"))
sz, a = load(src("carpet", "ao"))
save(sz, a, os.path.join(d, "carpet AmbientOcclusion.png"))
sz, h = load(src("carpet", "height16"))
save(sz, h, os.path.join(d, "carpet_DISP_16bit.png"), depth="16")
save(sz, c, os.path.join(d, "carpet_preview.jpg"), fmt="JPEG")
open(os.path.join(d, "readme.txt"), "w").write("downloaded from somewhere\n")

# 2) light panel: packed ARM, Poly Haven style names, delivered as a zip.
d = os.path.join(OUT, "_build_lightpanel")
sz, c = load(src("light_panel", "basecolor"))
save(sz, c, os.path.join(d, "LightPanel_BaseColor.png"))
_, ao = load(src("light_panel", "ao"))
_, ro = load(src("light_panel", "roughness"))
_, me = load(src("light_panel", "metallic"))
arm = ao.copy()
arm[:, 1], arm[:, 2] = ro[:, 0], me[:, 0]
save(sz, arm, os.path.join(d, "LightPanel_arm.png"))
_, n = load(src("light_panel", "normal_gl"))
save(sz, n, os.path.join(d, "LightPanel_nor_gl.png"))
_, e = load(src("light_panel", "emission"))
save(sz, e, os.path.join(d, "LightPanel_Emissive.png"))
_, h = load(src("light_panel", "height16"))
save(sz, h, os.path.join(d, "LightPanel_height.png"), depth="16")
with zipfile.ZipFile(os.path.join(OUT, "lightpanel_download.zip"), "w",
                     zipfile.ZIP_DEFLATED) as zf:
    for f in sorted(os.listdir(d)):
        zf.write(os.path.join(d, f), "LightPanel_2K/" + f)
shutil.rmtree(d)

# 3) wallpaper: words glued together, no separators, plus an unrelated mask.
d = os.path.join(OUT, "wallpaper_glued")
for kind, name in (("basecolor", "wallpaperalbedo.png"),
                   ("roughness", "wallpaperroughness.png"),
                   ("normal_gl", "wallpapernormal.png")):
    sz, px = load(src("wallpaper", kind))
    save(sz, px, os.path.join(d, name))
sz, h = load(src("wallpaper", "height16"))
save(sz, h, os.path.join(d, "wallpaperheight.png"), depth="16")
sz, m = load(os.path.join(SRC, "wallpaper", "procedural", "wallpaper_floor_grime_mask.png"))
save(sz, m, os.path.join(d, "wallpaper_floor_grime_mask.png"))

# 4) ceiling: ambientCG style, both GL and DX normals, two resolutions.
d = os.path.join(OUT, "ceiling_acg")
for kind, tag in (("basecolor", "Color"), ("roughness", "Roughness"),
                  ("metallic", "Metalness"), ("ao", "AmbientOcclusion")):
    sz, px = load(src("ceiling_tile", kind))
    save(sz, px, os.path.join(d, "Ceiling001_2K-PNG_%s.png" % tag))
sz, c = load(src("ceiling_tile", "basecolor"))
save(sz, c, os.path.join(d, "Ceiling001_1K-JPG_Color.jpg"), fmt="JPEG")
sz, n = load(src("ceiling_tile", "normal_gl"))
save(sz, n, os.path.join(d, "Ceiling001_2K-PNG_NormalGL.png"))
dx = n.copy()
dx[:, 1] = 1.0 - dx[:, 1]
save(sz, dx, os.path.join(d, "Ceiling001_2K-PNG_NormalDX.png"))
sz, h = load(src("ceiling_tile", "height16"))
save(sz, h, os.path.join(d, "Ceiling001_2K-PNG_Displacement.png"), depth="16")

# 5) a macro tint map copy for the variation test.
sz, t = load(os.path.join(SRC, "carpet", "macro", "carpet_macro_tint.png"))
save(sz, t, os.path.join(OUT, "variation", "big_tint_map.png"))
print("MESSY SETS DONE ->", OUT)

# Round-trip check: values read back must match what was written.
def back(path):
    img = bpy.data.images.load(path)
    img.colorspace_settings.is_data = True
    px = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    return img, px.reshape(-1, 4)
_, ref = load(src("carpet", "ao"))
img, got = back(os.path.join(OUT, "carpet_messy", "carpet AmbientOcclusion.png"))
print("ROUNDTRIP 8bit max diff", float(np.abs(ref[:, :3] - got[:, :3]).max()))
_, ref = load(src("carpet", "height16"))
img, got = back(os.path.join(OUT, "carpet_messy", "carpet_DISP_16bit.png"))
print("ROUNDTRIP 16bit max diff", float(np.abs(ref[:, :3] - got[:, :3]).max()),
      "is_float", img.is_float, "depth", img.depth)
