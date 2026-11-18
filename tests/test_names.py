"""Plain-Python test of the file-name guesser (no Blender needed).
Run:  python tests/test_names.py
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "source", "texture_tamer"))
import detect

CASES = {
    # ambientCG
    "Bricks076C_2K-PNG_Color.png": "BASE_COLOR", "Bricks076C_2K-PNG_NormalGL.png": "NORMAL_GL",
    "Bricks076C_2K-PNG_NormalDX.png": "NORMAL_DX", "Bricks076C_2K-PNG_Roughness.png": "ROUGHNESS",
    "Bricks076C_2K-PNG_Displacement.png": "HEIGHT", "Bricks076C_2K-PNG_AmbientOcclusion.png": "AO",
    "Metal032_4K-JPG_Metalness.jpg": "METALLIC", "Leaf001_2K-PNG_Opacity.png": "OPACITY",
    "Lamp_2K-PNG_Emission.png": "EMISSION",
    # Poly Haven
    "metal_plate_diff_2k.jpg": "BASE_COLOR", "metal_plate_nor_gl_2k.exr": "NORMAL_GL",
    "metal_plate_nor_dx_2k.exr": "NORMAL_DX", "metal_plate_rough_2k.exr": "ROUGHNESS",
    "metal_plate_metal_2k.exr": "METALLIC", "metal_plate_arm_2k.jpg": "ARM",
    "metal_plate_disp_2k.png": "HEIGHT", "metal_plate_ao_2k.jpg": "AO",
    # Poliigon
    "WoodPlanks028_COL_VAR1_3K.jpg": "BASE_COLOR", "WoodPlanks028_NRM_3K.png": "NORMAL_GL",
    "WoodPlanks028_GLOSS_3K.jpg": "GLOSS", "WoodPlanks028_REFL_3K.jpg": "SPECULAR",
    "WoodPlanks028_DISP16_3K.tif": "HEIGHT", "WoodPlanks028_AO_3K.jpg": "AO",
    "MetalRust_Metalness_4K_METALNESS.png": "METALLIC", "Poliigon_Brick_NormalGL_4K.png": "NORMAL_GL",
    # FreePBR
    "brick-wall_albedo.png": "BASE_COLOR", "brick-wall_normal-ogl.png": "NORMAL_GL",
    "brick-wall_height.png": "HEIGHT", "brick-wall_metallic.png": "METALLIC",
    "brick-wall_roughness.png": "ROUGHNESS", "brick-wall_preview.jpg": "IGNORE",
    "brick-wall_normal-dx.png": "NORMAL_DX",
    # Quixel / Megascans
    "vgvmeauaw_2K_Albedo.jpg": "BASE_COLOR", "vgvmeauaw_2K_Normal.jpg": "NORMAL_GL",
    "vgvmeauaw_2K_Roughness.jpg": "ROUGHNESS", "vgvmeauaw_2K_Displacement.exr": "HEIGHT",
    "vgvmeauaw_2K_Cavity.jpg": "IGNORE", "vgvmeauaw_2K_Gloss.jpg": "GLOSS",
    "vgvmeauaw_2K_Specular.jpg": "SPECULAR", "vgvmeauaw_2K_Translucency.jpg": "IGNORE",
    "vgvmeauaw_2K_Bump.jpg": "BUMP", "vgvmeauaw_2K_Opacity.jpg": "OPACITY",
    # Substance / Unreal exports
    "Mat_Base_color.png": "BASE_COLOR", "Mat_Normal_OpenGL.png": "NORMAL_GL",
    "Mat_Normal_DirectX.png": "NORMAL_DX", "Mat_Mixed_AO.png": "AO",
    "T_Rock_OcclusionRoughnessMetallic.png": "ARM", "T_Rock_ORM.png": "ARM",
    # Backrooms sets
    "light_panel_procedural_emission.png": "EMISSION", "carpet_procedural_height16.png": "HEIGHT",
    "carpet_procedural_normal_gl.png": "NORMAL_GL", "baseboard_procedural_basecolor.png": "BASE_COLOR",
    "wallpaper_floor_grime_mask.png": "IGNORE",
    # Messy
    "IMG_2034 Carpet Diffuse (1).jpg": "BASE_COLOR", "carpet-NRM-DX.png": "NORMAL_DX",
    "Carpet_GLOSS.png": "GLOSS", "carpet AmbientOcclusion.png": "AO",
    "carpet_DISP_16bit.png": "HEIGHT", "wallpaperalbedo.png": "BASE_COLOR",
    "wallpapernormal.png": "NORMAL_GL", "wallpaperroughness.png": "ROUGHNESS",
    "wallpaperheight.png": "HEIGHT", "texture_metalness copy.png": "METALLIC",
    "Stone Wall - Gloss.JPG": "GLOSS", "albedo.png": "BASE_COLOR",
    "random_photo.jpg": "IGNORE",
}
bad = 0
for name, want in CASES.items():
    got = detect.classify(name)[0]
    if got != want:
        bad += 1
        print("FAIL %-45s want %-11s got %s" % (name, want, got))
print("%d/%d names recognised correctly" % (len(CASES) - bad, len(CASES)))
# A set with both a roughness and a gloss map: only one may feed Roughness.
items = {os.path.basename(i["path"]): i["type"] for i in
         detect.detect_files(["x/Rock_Roughness.png", "x/Rock_Gloss.png", "x/Rock_Color.png"])}
if items != {"Rock_Roughness.png": "ROUGHNESS", "Rock_Gloss.png": "IGNORE", "Rock_Color.png": "BASE_COLOR"}:
    bad += 1
    print("FAIL roughness + gloss in one set:", items)
else:
    print("roughness + gloss in one set: gloss left unused")
# Several emission maps in one set (baked ceiling with lights): the plain
# "..._emission" is used, the variants stay in the list as unused, even when a
# variant is the biggest file. The set's JSON gives the emission strength.
import json
import tempfile
EM_NAMES = ["ceiling_lit_default_2k_" + n for n in (
    "basecolor.png", "normal_gl.png", "roughness.png", "height16.png", "ao.png",
    "emission.png", "emission_all_on.png", "emission_some_off.png",
    "emission_dim.png", "emission_mask.png")]
with tempfile.TemporaryDirectory() as tmp:
    for n in EM_NAMES:
        with open(os.path.join(tmp, n), "wb") as f:
            f.write(b"x" * (900 if "all_on" in n else 100))   # variant is the biggest
    with open(os.path.join(tmp, "ceiling_lit_default_2k_info.json"), "w") as f:
        json.dump({"tile_size_m": [4.8768, 4.8768], "emission_strength_hint": 20.0}, f)
    for label, folder in (("fake ceiling folder", tmp),
                          ("real ceiling folder",
                           "D:/Blender/backrooms_pbr/ceiling_lit/default/2k")):
        if not os.path.isdir(folder):
            print("skipped (missing):", folder)
            continue
        paths = [os.path.join(folder, n) for n in sorted(os.listdir(folder))]
        res = {os.path.basename(i["path"]).split("2k_")[-1]: i["type"]
               for i in detect.detect_files(paths)}
        use = [n for n, t in res.items() if t == "EMISSION"]
        if use != ["emission.png"]:
            bad += 1
            print("FAIL %s: emission file used:" % label, use)
        elif any(res[n] != "IGNORE" for n in res if n.startswith("emission_")):
            bad += 1
            print("FAIL %s: emission variants should be unused:" % label, res)
        else:
            print("%s: plain emission used, variants unused" % label)
        hint = detect.find_info_emission_strength(folder)
        if hint != 20.0:
            bad += 1
            print("FAIL %s: emission_strength_hint:" % label, hint)
    # Missing / bad hints give None.
    for body in ('{"tile_size_m": 1}', '{"emission_strength_hint": "20"}',
                 '{"emission_strength_hint": 0}', '{"emission_strength_hint": true}',
                 '{"emission_strength_hint": -3}', "not json", "[20]"):
        with open(os.path.join(tmp, "ceiling_lit_default_2k_info.json"), "w") as f:
            f.write(body)
        if detect.find_info_emission_strength(tmp) is not None:
            bad += 1
            print("FAIL bad emission hint accepted:", body)
    if detect.find_info_emission_strength(os.path.join(tmp, "nope")) is not None:
        bad += 1
        print("FAIL hint from missing folder")
# The tie-break only looks at words after the map word (sizes do not count).
for name, want in (("x_emission.png", []), ("x_emission_2k.png", []),
                   ("x_emission_all_on.png", ["all", "on"]),
                   ("x_Normal_GL.png", []), ("x_ambient_occlusion_dim.png", ["dim"])):
    if detect.trailing_words(name) != want:
        bad += 1
        print("FAIL trailing_words(%s) = %s" % (name, detect.trailing_words(name)))
sys.exit(1 if bad else 0)
