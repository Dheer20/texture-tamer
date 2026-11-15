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
sys.exit(1 if bad else 0)
