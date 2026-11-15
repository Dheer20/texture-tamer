"""Open Blender with a window, apply a test set, screenshot the PBR panel, quit.

Run (from D:/Blender/pbr_quick_apply, after tests/run_tests.sh installed the zip):
  blender -b --factory-startup --python-expr "import bpy; bpy.ops.wm.save_as_mainfile(filepath='tests/renders/_ui_start.blend')"
  BLENDER_USER_RESOURCES=tests/_blender_user blender --factory-startup --window-geometry 0 0 1500 1000 tests/renders/_ui_start.blend --python tests/screenshot_panel.py
Opening a saved file skips the splash screen. A Blender window appears for
about 15 seconds and closes by itself. For the screenshots only, the Texture Tamer panels
are moved into the sidebar's first tab (a script cannot pick the open tab) and
the sidebar is scrolled to show the lower part. Screenshots go to
tests/renders/ui_*.png; panel drawing errors show in the console output.
"""
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "renders")
DATA = os.path.join(HERE, "data")
os.makedirs(OUT, exist_ok=True)

bpy.ops.preferences.addon_enable(module="bl_ext.user_default.texture_tamer")

# Screenshot-only: show our panels in the sidebar's first tab ("Item").
_mod = sys.modules["bl_ext.user_default.texture_tamer"]
_ours = [c for c in _mod.classes if c.__name__.endswith("_view3d")]
for _c in reversed(_ours):
    bpy.utils.unregister_class(_c)
for _name in ("VIEW3D_PT_transform", "VIEW3D_PT_context_properties"):
    _b = getattr(bpy.types, _name, None)
    if _b:
        bpy.utils.unregister_class(_b)
for _c in _ours:
    _c.bl_category = "Item"
    # Open the sections worth seeing; fold the rest so it fits.
    if "repeats" in _c.__name__:
        _c.bl_options = {"DEFAULT_CLOSED"}
    elif "_main_" not in _c.__name__:
        _c.bl_options = set()
    bpy.utils.register_class(_c)


def view3d():
    win = bpy.context.window_manager.windows[0]
    for area in win.screen.areas:
        if area.type == "VIEW_3D":
            return win, area
    return win, None


def setup():
    win, area = view3d()
    with bpy.context.temp_override(window=win, area=area):
        cube = bpy.data.objects.get("Cube")
        if cube:
            bpy.context.view_layer.objects.active = cube
            cube.select_set(True)
        bpy.ops.pbrqa.load_texture_set("EXEC_DEFAULT", directory=DATA + "/carpet_messy/")
    mat = bpy.context.active_object.active_material
    mat.pbrqa.index = [i for i, it in enumerate(mat.pbrqa.maps)
                       if it.map_type == "BASE_COLOR"][0]
    sp = area.spaces.active
    sp.show_region_ui = True
    sp.shading.type = "MATERIAL"
    return 5.0  # thumbnails are made in the background


COMBOS = [("CHANNEL", "SIZE_FIRST"), ("LIST", "HEADER"), ("GRID", "CLASSIC"), ("FULL", "CLASSIC")]


def _shoot(name):
    win, area = view3d()
    with bpy.context.temp_override(window=win, area=area):
        bpy.ops.screen.screenshot(filepath=os.path.join(OUT, name))


def _scroll_to_maps():
    win, area = view3d()
    ui = [r for r in area.regions if r.type == "UI"][0]
    with bpy.context.temp_override(window=win, area=area, region=ui):
        for _i in range(30):
            bpy.ops.view2d.scroll_down(page=False)
    area.tag_redraw()


def make_step(i):
    def step():
        prefs = bpy.context.preferences.addons["bl_ext.user_default.texture_tamer"].preferences
        if i > 0:  # shoot the previous combination, then switch
            _shoot("ui_layout_%s_%s.png" % (COMBOS[i - 1][0].lower(), COMBOS[i - 1][1].lower()))
        if i == len(COMBOS):
            print("UI SCREENSHOTS DONE")
            bpy.ops.wm.quit_blender()
            return None
        prefs.maps_layout, prefs.placement_layout = COMBOS[i]
        _scroll_to_maps()
        view3d()[1].tag_redraw()
        return 2.5
    return step


steps = [setup] + [make_step(i) for i in range(len(COMBOS) + 1)]


def runner():
    if not steps:
        return None
    nxt = steps.pop(0)()
    return nxt if nxt is not None else (0.5 if steps else None)


bpy.app.timers.register(runner, first_interval=2.0)
