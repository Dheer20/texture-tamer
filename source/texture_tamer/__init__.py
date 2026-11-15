# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dheer
"""Texture Tamer: turn any PBR texture folder, zip or image into a
finished Principled BSDF material in one step."""

import math
import os
import zipfile

import bpy
import bpy.utils.previews
from bl_operators.presets import AddPresetBase
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty,
                       FloatProperty, IntProperty, PointerProperty,
                       StringProperty)

from . import build, detect

EXT_GLOB = ";".join("*" + e for e in sorted(detect.IMAGE_EXTS)) + ";*.zip"
PRESET_DIR = "texture_tamer/tile_size"

# Built-in sizes in the Preset menu: (label, metres).
FIXED_SIZES = [("0.25 m", 0.25), ("0.5 m", 0.5), ("1 m", 1.0), ("2 m", 2.0),
               ("1 ft", 0.3048), ("2 ft", 0.6096), ("4 ft", 1.2192)]

PROJ_HELP = {
    "UV": "Follows the object's unwrap. Best for most models",
    "BOX": "No unwrap needed: projects from the 6 sides of the object",
    "WORLD": "Runs on across separate objects; stays put if one moves",
}
# One-line versions that fit the sidebar.
PROJ_SHORT = {
    "UV": "Follows the object's unwrap",
    "BOX": "No unwrap needed (6 sides)",
    "WORLD": "Runs on across objects",
}


# ---------------------------------------------------------------- properties
def _owner_material(item):
    idb = item.id_data
    return idb if isinstance(idb, bpy.types.Material) else None


def _on_type_change(self, context):
    mat = _owner_material(self)
    if mat and mat.pbrqa.managed:
        build.build(mat)  # correcting a guess after applying: rebuild at once


def _on_map_type(self, context):
    """Same rule in every layout and in the check-first list: one file per channel.
    Giving a file a type takes that channel over; the old file becomes unused."""
    idb = self.id_data
    coll = None
    if isinstance(idb, bpy.types.Material):
        coll = idb.pbrqa.maps
    elif isinstance(idb, bpy.types.Scene):
        coll = idb.pbrqa_pending.maps
    ch = _channel_of(self.map_type)
    if coll is not None and ch:
        me = self.as_pointer()
        for other in coll:
            if other.as_pointer() != me and _channel_of(other.map_type) == ch:
                other["map_type"] = detect.MAP_IDS.index("IGNORE")
    _on_type_change(self, context)


def _on_value(self, context):
    mat = self.id_data
    if isinstance(mat, bpy.types.Material) and mat.pbrqa.managed:
        build.apply_values(mat)


def _on_rebuild(self, context):
    mat = self.id_data
    if isinstance(mat, bpy.types.Material) and mat.pbrqa.managed:
        build.build(mat)


def _on_linked(self, context):
    if not self.size_linked:
        # Unlinking starts from the height you were already seeing.
        self["tile_height"] = self.tile_size * (self.aspect or 1.0)
    _on_value(self, context)


class PBRQA_MapItem(bpy.types.PropertyGroup):
    filepath: StringProperty(name="File", subtype="FILE_PATH")
    enabled: BoolProperty(
        name="Use", default=True,
        description="Use this map. Untick to see the material without it",
        update=_on_type_change)
    map_type: EnumProperty(
        name="Map Type", items=detect.MAP_TYPES, default="IGNORE",
        description="What this image is used for. Change it if the guess is wrong "
        "(the file that had this job before becomes unused)",
        update=_on_map_type)
    guess: StringProperty(name="Guess")

    def label_for_node(self):
        return "%s: %s" % (detect.MAP_LABEL.get(self.map_type, self.map_type),
                           os.path.basename(self.filepath))


class PBRQA_Pending(bpy.types.PropertyGroup):
    maps: CollectionProperty(type=PBRQA_MapItem)
    index: IntProperty()
    source: StringProperty()
    set_name: StringProperty()


class PBRQA_MaterialSettings(bpy.types.PropertyGroup):
    managed: BoolProperty(default=False)
    maps: CollectionProperty(type=PBRQA_MapItem)
    index: IntProperty()
    source: StringProperty(name="Source")
    aspect: FloatProperty(default=1.0)
    has_height: BoolProperty()
    has_normal: BoolProperty()
    has_bump: BoolProperty()
    has_emission: BoolProperty()
    has_ao: BoolProperty()
    has_tint: BoolProperty()
    info_width: FloatProperty(default=0.0, subtype="DISTANCE", unit="LENGTH")
    info_height: FloatProperty(default=0.0, subtype="DISTANCE", unit="LENGTH")
    tint_auto: BoolProperty(default=False)
    solo_index: IntProperty(
        name="Show One Map", default=-1,
        description="Show only this map on the object, to check it", update=_on_rebuild)

    # --- Placement ---
    projection: EnumProperty(
        name="Projection",
        items=[("UV", "UV Map", PROJ_HELP["UV"]),
               ("BOX", "Box", PROJ_HELP["BOX"] + ". Apply the object's scale first"),
               ("WORLD", "World", PROJ_HELP["WORLD"])],
        default="UV", update=_on_rebuild)
    tile_size: FloatProperty(
        name="Size", subtype="DISTANCE", unit="LENGTH", default=1.0,
        min=0.001, soft_min=0.05, soft_max=20.0, step=10,
        description="Real-world width of one repeat of the texture",
        update=_on_value)
    tile_height: FloatProperty(
        name="Height", subtype="DISTANCE", unit="LENGTH", default=1.0,
        min=0.001, soft_min=0.05, soft_max=20.0, step=10,
        description="Real-world height of one repeat of the texture",
        update=_on_value)
    size_linked: BoolProperty(
        name="Keep Texture Shape", default=True,
        description="On: height follows width, so the texture never stretches. "
        "Off: set width and height separately", update=_on_linked)
    uv_metres: FloatProperty(
        name="UV Square Size", subtype="DISTANCE", unit="LENGTH", default=1.0,
        min=0.0001,
        description="How many metres one full UV square covers on the object",
        update=_on_value)
    rotation: FloatProperty(
        name="Rotation", subtype="ANGLE", default=0.0,
        description="Turn the texture on the surface", update=_on_value)
    offset_x: FloatProperty(
        name="Offset X", subtype="DISTANCE", unit="LENGTH", default=0.0, step=10,
        description="Slide the texture sideways", update=_on_value)
    offset_y: FloatProperty(
        name="Offset Y", subtype="DISTANCE", unit="LENGTH", default=0.0, step=10,
        description="Slide the texture up or down", update=_on_value)
    check_grid: EnumProperty(
        name="Check Size",
        items=[("OFF", "Off", "Show the material normally"),
               ("TILES", "Tiles", "Blue/white squares over the object: one square = "
                "one repeat of the texture. Switch off before rendering"),
               ("METRES", "Metres", "Squares of 1 m x 1 m, to check the object's own "
                "size. Switch off before rendering")],
        default="OFF", update=_on_rebuild)

    # --- Break up repeats ---
    random_offset: BoolProperty(
        name="Shift", default=False,
        description="Every object using this material gets its own shift, so "
        "neighbouring walls don't line up", update=_on_rebuild)
    random_turn: BoolProperty(
        name="Turn", default=False,
        description="Every object using this material gets its own quarter turn "
        "(0, 90, 180 or 270 degrees)", update=_on_rebuild)
    tint_enabled: BoolProperty(
        name="Variation Map", default=True,
        description="Multiply a large colour map over the texture to hide repeats",
        update=_on_rebuild)
    tint_path: StringProperty(
        name="Variation Map", subtype="FILE_PATH",
        description="Large colour map multiplied over the base colour to "
        "break up visible repeats", update=_on_rebuild)
    tint_size: FloatProperty(
        name="Size", subtype="DISTANCE", unit="LENGTH", default=5.0,
        min=0.01, soft_max=100.0,
        description="Real-world width of one repeat of the variation map",
        update=_on_value)
    tint_strength: FloatProperty(
        name="Strength", default=1.0, min=0.0, max=1.0,
        subtype="FACTOR", description="How much the variation map tints the "
        "colour", update=_on_value)

    # --- Surface ---
    normal_strength: FloatProperty(
        name="Normal Strength", default=1.0, min=0.0, soft_max=3.0,
        description="How strong the normal map's surface detail looks",
        update=_on_value)
    bump_strength: FloatProperty(
        name="Bump Strength", default=0.5, min=0.0, max=1.0,
        description="How strong the bump map looks", update=_on_value)
    displacement_mode: EnumProperty(
        name="Displacement",
        items=[("OFF", "Off", "Height map not used. Safest: nothing moves or bulges"),
               ("BUMP", "Bump", "Height map used as fake surface detail; no geometry "
                "moves. Most useful when the set has no normal map"),
               ("REAL", "Real", "Height map really moves the surface (plus bump). "
                "Needs a finely subdivided object, or you get spikes and seams")],
        default="OFF", update=_on_rebuild)
    displacement_height: FloatProperty(
        name="Amount", subtype="DISTANCE", unit="LENGTH", default=0.01,
        min=0.0, soft_max=0.2,
        description="Distance between the lowest and highest point of the "
        "height map. Real displacement needs enough geometry (see Subdivide)",
        update=_on_value)
    displacement_midlevel: FloatProperty(
        name="Midlevel", default=0.5, min=0.0, max=1.0,
        description="Height map value that stays on the surface. 0.5 for most "
        "downloads; 0 if black means 'flat surface'", update=_on_value)
    emission_strength: FloatProperty(
        name="Emission Strength", default=1.0, min=0.0, soft_max=50.0,
        description="Brightness of the glow from the emission map",
        update=_on_value)
    ao_strength: FloatProperty(
        name="AO Strength", default=1.0, min=0.0, max=1.0, subtype="FACTOR",
        description="How much the AO map darkens the colour. Lower it if "
        "crevices look too dark", update=_on_value)


# ---------------------------------------------------------------- helpers
def _unzip(path):
    """Unpack image files from a zip into a folder next to it. Returns the folder."""
    target = os.path.splitext(path)[0]
    os.makedirs(target, exist_ok=True)
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            name = info.filename
            if info.is_dir() or os.path.splitext(name)[1].lower() not in detect.IMAGE_EXTS:
                continue
            # zipfile.extract strips "..", drive letters and leading slashes.
            dest = os.path.join(target, *[p for p in name.replace("\\", "/").split("/")
                                          if p not in ("", ".", "..")])
            if not os.path.isfile(dest):
                zf.extract(info, target)
    return target


def _images_in(folder):
    files = [os.path.join(folder, f) for f in os.listdir(folder)
             if os.path.splitext(f)[1].lower() in detect.IMAGE_EXTS]
    if not files:  # zips often hold one sub-folder
        for root, _dirs, names in os.walk(folder):
            files += [os.path.join(root, f) for f in names
                      if os.path.splitext(f)[1].lower() in detect.IMAGE_EXTS]
    return files


def gather(directory, filenames, filepath=""):
    """Turn whatever the user picked or dropped into (image paths, preferred set, source)."""
    names = [f for f in filenames if f]
    picked = [os.path.join(directory, f) for f in names] if directory else []
    if not picked and filepath:
        picked = [filepath] if os.path.isfile(filepath) else []
        directory = directory or (filepath if os.path.isdir(filepath)
                                  else os.path.dirname(filepath))
    zips = [p for p in picked if p.lower().endswith(".zip")]
    if zips:
        folder = _unzip(zips[0])
        return _images_in(folder), None, zips[0]
    images = [p for p in picked if os.path.splitext(p)[1].lower() in detect.IMAGE_EXTS]
    if len(images) > 1:
        return images, None, directory
    if len(images) == 1:
        folder = os.path.dirname(images[0])
        return _images_in(folder), detect.classify(images[0])[1], folder
    if directory and os.path.isdir(directory):
        return _images_in(directory), None, directory
    return [], None, directory


def _fill(collection, items):
    collection.clear()
    for it in items:
        row = collection.add()
        row["map_type"] = detect.MAP_IDS.index(it["type"])  # no update callback
        row["enabled"] = it.get("enabled", True)
        row.filepath = it["path"]
        row.guess = it["guess"]


def _targets(context):
    objs = [o for o in context.selected_objects
            if o.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"}]
    act = context.active_object
    if act and act.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"} and act not in objs:
        objs.insert(0, act)
    return objs


def _use_info_size(s):
    """Set the tile size from the set's own size file (or 1 m). No rebuild."""
    if s.info_width > 0:
        w, h = s.info_width, s.info_height or s.info_width
        s["tile_size"] = w
        shape_matches = abs(h / w - (s.aspect or 1.0)) < 0.02
        s["size_linked"] = shape_matches
        s["tile_height"] = h
    else:
        s["tile_size"] = 1.0
        s["size_linked"] = True


def apply_items(context, items, name, source):
    """Create the material, build it, put it on the selected objects."""
    mat = bpy.data.materials.new(name or "PBR_Material")
    s = mat.pbrqa
    s.managed = True
    s.source = source or ""
    for it in items:
        row = s.maps.add()
        row["map_type"] = detect.MAP_IDS.index(it["type"])
        row["enabled"] = it.get("enabled", True)
        row.filepath = it["path"]
        row.guess = it["guess"]
    objs = _targets(context)
    act = context.active_object if context.active_object in objs else (objs[0] if objs else None)
    uvm = build.measure_uv_metres(act)
    if uvm:
        s["uv_metres"] = uvm
    elif act is not None:
        s["projection"] = 1  # BOX: no UV map to use

    used = [it["path"] for it in items if it["type"] != "IGNORE"]
    folder = os.path.dirname(used[0]) if used else ""
    info = detect.find_info_size(folder) if folder else None
    dinfo = detect.find_info_displacement(folder) if folder else None
    if dinfo:  # the set says how deep its height map is: use that
        s["displacement_height"], s["displacement_midlevel"] = dinfo
    if info:
        s["info_width"], s["info_height"] = info
    var = detect.find_variation_map(folder) if folder else None
    if var:
        s["tint_path"] = var
        s["tint_auto"] = True
        tinfo = detect.find_info_size(os.path.dirname(var))
        if tinfo:
            s["tint_size"] = tinfo[0]

    build.build(mat)          # loads the images, so the texture shape is known
    _use_info_size(s)
    build.apply_values(mat)
    for o in objs:
        if o.material_slots:
            o.active_material = mat
        else:
            o.data.materials.append(mat)
    return mat, len(objs)


def _active_mat(context):
    sd = getattr(context, "space_data", None)
    if sd and sd.type == "NODE_EDITOR":
        mat = getattr(sd, "id", None)
        if isinstance(mat, bpy.types.Material):
            return mat
    ob = context.active_object
    return ob.active_material if ob else None


def _length(context, v):
    """A length as Blender shows it with the scene's units (m, cm, ft...)."""
    us = context.scene.unit_settings
    try:
        return bpy.utils.units.to_string(us.system, "LENGTH", v * us.scale_length,
                                         precision=2, split_unit=us.use_separate)
    except Exception:
        return "%.2f m" % v


# ---------------------------------------------------------------- operators
class PBRQA_OT_load(bpy.types.Operator):
    """Pick a texture folder, a zip, or any one image of a set, and build a material"""
    bl_idname = "pbrqa.load_texture_set"
    bl_label = "Apply Texture Set"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})
    directory: StringProperty(subtype="DIR_PATH", options={"SKIP_SAVE"})
    files: CollectionProperty(type=bpy.types.OperatorFileListElement,
                              options={"HIDDEN", "SKIP_SAVE"})
    filter_glob: StringProperty(default=EXT_GLOB, options={"HIDDEN"})
    filter_folder: BoolProperty(default=True, options={"HIDDEN"})
    apply_now: BoolProperty(
        name="Apply Right Away", default=True,
        description="Build the material straight away. Turn off to check the "
        "detected maps first")

    def invoke(self, context, event):
        if self.properties.is_property_set("directory") or \
                self.properties.is_property_set("filepath"):
            return self.execute(context)  # dropped onto the window
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        self.layout.prop(self, "apply_now")
        self.layout.label(text="Folder, zip, or one image of the set", icon="INFO")

    def execute(self, context):
        try:
            paths, key, source = gather(self.directory,
                                        [f.name for f in self.files], self.filepath)
        except (OSError, zipfile.BadZipFile) as err:
            self.report({"ERROR"}, "Could not read the files: %s" % err)
            return {"CANCELLED"}
        items = detect.detect_files(paths, key)
        used = [i for i in items if i["type"] != "IGNORE"]
        if not used:
            self.report({"WARNING"}, "No texture maps recognised in %s" % (source or "selection"))
            return {"CANCELLED"}
        name = detect.set_name(items)
        if self.apply_now and _targets(context):
            mat, n = apply_items(context, items, name, source)
            self.report({"INFO"}, "%s: %d maps on %d object(s)" % (mat.name, len(used), n))
        else:
            pend = context.scene.pbrqa_pending
            _fill(pend.maps, items)
            pend.source, pend.set_name = source or "", name
            if self.apply_now:
                self.report({"WARNING"}, "Nothing selected: check the list, then Apply")
        return {"FINISHED"}


class PBRQA_OT_apply_pending(bpy.types.Operator):
    """Build a material from the list above and put it on the selected objects"""
    bl_idname = "pbrqa.apply_pending"
    bl_label = "Apply to Selected"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if not _targets(context):
            cls.poll_message_set("Select an object first")
            return False
        return len(context.scene.pbrqa_pending.maps) > 0

    def execute(self, context):
        pend = context.scene.pbrqa_pending
        items = [{"path": m.filepath, "type": m.map_type, "guess": m.guess,
                  "enabled": m.enabled} for m in pend.maps]
        mat, n = apply_items(context, items, pend.set_name, pend.source)
        pend.maps.clear()
        self.report({"INFO"}, "%s applied to %d object(s)" % (mat.name, n))
        return {"FINISHED"}


class PBRQA_OT_clear_pending(bpy.types.Operator):
    """Forget the scanned list"""
    bl_idname = "pbrqa.clear_pending"
    bl_label = "Clear"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        context.scene.pbrqa_pending.maps.clear()
        return {"FINISHED"}


class _MatOp:
    @classmethod
    def poll(cls, context):
        mat = _active_mat(context)
        return bool(mat and mat.pbrqa.managed)


class PBRQA_OT_rebuild(_MatOp, bpy.types.Operator):
    """Rebuild this material's nodes from the map list (hand edits to its nodes are lost)"""
    bl_idname = "pbrqa.rebuild"
    bl_label = "Rebuild Material"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        build.build(_active_mat(context))
        return {"FINISHED"}


class PBRQA_OT_measure(_MatOp, bpy.types.Operator):
    """Measure the object's UV map again. Use it after changing the object's UVs,
so Size stays in real metres"""
    bl_idname = "pbrqa.measure_uv"
    bl_label = "Measure UVs"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        u = build.measure_uv_metres(context.active_object)
        if not u:
            self.report({"WARNING"}, "Active object has no usable UV map")
            return {"CANCELLED"}
        _active_mat(context).pbrqa.uv_metres = u
        return {"FINISHED"}


class PBRQA_OT_set_size(_MatOp, bpy.types.Operator):
    """Use this tile size"""
    bl_idname = "pbrqa.set_size"
    bl_label = "Set Tile Size"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    width: FloatProperty(name="Width", subtype="DISTANCE", unit="LENGTH", default=1.0, min=0.001)
    height: FloatProperty(name="Height", subtype="DISTANCE", unit="LENGTH", default=0.0, min=0.0,
                          description="0 = follow the texture's shape")

    def execute(self, context):
        s = _active_mat(context).pbrqa
        keep_shape = self.height <= 0 or abs(self.height / self.width - (s.aspect or 1.0)) < 0.02
        s["size_linked"] = keep_shape
        s["tile_height"] = self.height if self.height > 0 else self.width * (s.aspect or 1.0)
        s.tile_size = self.width  # update pushes the values into the nodes
        return {"FINISHED"}


class PBRQA_MT_size_presets(bpy.types.Menu):
    bl_label = "Size Presets"
    preset_subdir = PRESET_DIR
    preset_operator = "script.execute_preset"
    preset_add_operator = "pbrqa.size_preset_add"

    def draw(self, context):
        layout = self.layout
        mat = _active_mat(context)
        s = mat.pbrqa if mat else None
        if s and s.info_width > 0:
            h = s.info_height or s.info_width
            op = layout.operator(PBRQA_OT_set_size.bl_idname, icon="FILE_TEXT",
                                 text="From Texture Info  (%s x %s)" % (
                                     _length(context, s.info_width), _length(context, h)))
            op.width, op.height = s.info_width, h
            layout.separator()
        for label, v in FIXED_SIZES:
            op = layout.operator(PBRQA_OT_set_size.bl_idname, text=label)
            op.width, op.height = v, 0.0
        layout.separator()
        if bpy.utils.preset_paths(self.preset_subdir):
            bpy.types.Menu.draw_preset(self, context)
            layout.separator()
        layout.operator_context = "INVOKE_DEFAULT"
        layout.operator(PBRQA_OT_size_preset_add.bl_idname, text="Save Current Size...",
                        icon="ADD")


class PBRQA_OT_size_preset_add(AddPresetBase, bpy.types.Operator):
    """Save the current tile size as a preset"""
    bl_idname = "pbrqa.size_preset_add"
    bl_label = "Add Size Preset"
    preset_menu = "PBRQA_MT_size_presets"
    preset_subdir = PRESET_DIR
    preset_defines = ["mat = bpy.context.object.active_material"]
    preset_values = ["mat.pbrqa.size_linked", "mat.pbrqa.tile_height", "mat.pbrqa.tile_size"]


class PBRQA_OT_turn(_MatOp, bpy.types.Operator):
    """Turn the texture a quarter turn"""
    bl_idname = "pbrqa.turn"
    bl_label = "Turn Texture"
    bl_options = {"REGISTER", "UNDO"}

    degrees: FloatProperty(name="Degrees", default=90.0)

    def execute(self, context):
        s = _active_mat(context).pbrqa
        new = math.degrees(s.rotation) + self.degrees
        s.rotation = math.radians(round(new % 360.0, 4))
        return {"FINISHED"}


def _longest_side(obj):
    d = sorted(obj.dimensions, reverse=True) if obj else [0]
    return d[0]


class PBRQA_OT_fit(_MatOp, bpy.types.Operator):
    """Change the tile size so a whole number of tiles fits across the selected
object's longest side (no cut-off tile at the edge)"""
    bl_idname = "pbrqa.fit_to_object"
    bl_label = "Fit to Object"
    bl_options = {"REGISTER", "UNDO"}

    tiles_across: IntProperty(
        name="Tiles Across", default=1, min=1, soft_max=50,
        description="How many whole tiles fit across the object's longest side")

    @classmethod
    def poll(cls, context):
        if not super().poll(context):
            return False
        if _longest_side(context.active_object) <= 0:
            cls.poll_message_set("Select the object to fit to")
            return False
        return True

    def execute(self, context):
        s = _active_mat(context).pbrqa
        ob = context.active_object
        length = _longest_side(ob)
        if s.projection == "UV":
            u = build.measure_uv_metres(ob)
            if u:
                s["uv_metres"] = u
        if not self.properties.is_property_set("tiles_across"):
            self.tiles_across = max(1, round(length / max(s.tile_size, 1e-6)))
        h_ratio = build.tile_height(s) / max(s.tile_size, 1e-6)
        w = length / self.tiles_across
        if not s.size_linked:
            s["tile_height"] = w * h_ratio
        s.tile_size = w
        return {"FINISHED"}


class PBRQA_OT_reset(_MatOp, bpy.types.Operator):
    """Put size, rotation, offset and projection back to how they were when applied"""
    bl_idname = "pbrqa.reset_placement"
    bl_label = "Reset"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        mat = _active_mat(context)
        s = mat.pbrqa
        ob = context.active_object
        u = build.measure_uv_metres(ob)
        if u:
            s["uv_metres"] = u
        s["projection"] = 0 if (u or ob is None) else 1
        s["rotation"] = 0.0
        s["offset_x"] = s["offset_y"] = 0.0
        s["check_grid"] = 0
        _use_info_size(s)
        build.build(mat)
        return {"FINISHED"}


class PBRQA_OT_material_preview(bpy.types.Operator):
    """Textures are hidden in Solid view. Switch this 3D Viewport to Material Preview"""
    bl_idname = "pbrqa.material_preview"
    bl_label = "Show Material Preview"

    @classmethod
    def poll(cls, context):
        return getattr(context.space_data, "type", "") == "VIEW_3D"

    def execute(self, context):
        context.space_data.shading.type = "MATERIAL"
        return {"FINISHED"}


class PBRQA_OT_load_tint(_MatOp, bpy.types.Operator):
    """Choose a large variation / tint image to multiply over the base colour"""
    bl_idname = "pbrqa.load_tint"
    bl_label = "Add Variation Map"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})
    filter_glob: StringProperty(default=EXT_GLOB.replace(";*.zip", ""), options={"HIDDEN"})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        if not os.path.isfile(self.filepath):
            return {"CANCELLED"}
        s = _active_mat(context).pbrqa
        s["tint_auto"] = False
        s["tint_enabled"] = True
        s.tint_path = self.filepath  # rebuilds
        return {"FINISHED"}


class PBRQA_OT_remove_tint(_MatOp, bpy.types.Operator):
    """Remove the variation map"""
    bl_idname = "pbrqa.remove_tint"
    bl_label = "Remove Variation Map"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = _active_mat(context).pbrqa
        s["tint_auto"] = False
        s.tint_path = ""
        return {"FINISHED"}


class PBRQA_OT_subdivide(bpy.types.Operator):
    """Add a Simple Subdivision modifier so real displacement has geometry to move"""
    bl_idname = "pbrqa.add_subdivision"
    bl_label = "Subdivide for Displacement"
    bl_options = {"REGISTER", "UNDO"}

    levels: IntProperty(name="Levels", default=4, min=1, max=6,
                        description="More levels = finer displacement, slower")

    @classmethod
    def poll(cls, context):
        return bool(context.active_object and context.active_object.type == "MESH")

    def execute(self, context):
        for o in _targets(context):
            if o.type != "MESH":
                continue
            mod = o.modifiers.get("PBR Displacement") or \
                o.modifiers.new("PBR Displacement", "SUBSURF")
            mod.subdivision_type = "SIMPLE"
            mod.levels = mod.render_levels = self.levels
        return {"FINISHED"}


class PBRQA_OT_solo_map(_MatOp, bpy.types.Operator):
    """Show only this map on the object, to check it. Click again to show the whole material"""
    bl_idname = "pbrqa.solo_map"
    bl_label = "Show This Map Only"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    index: IntProperty(default=-1)

    def execute(self, context):
        s = _active_mat(context).pbrqa
        s.solo_index = -1 if self.index == s.solo_index else self.index
        return {"FINISHED"}


class PBRQA_OT_add_map(_MatOp, bpy.types.Operator):
    """Add an image the scan missed; its type is guessed from the name (change it in the list)"""
    bl_idname = "pbrqa.add_map"
    bl_label = "Add Map"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})
    filter_glob: StringProperty(default=EXT_GLOB.replace(";*.zip", ""), options={"HIDDEN"})
    channel: StringProperty(default="", options={"SKIP_SAVE", "HIDDEN"})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        if not os.path.isfile(self.filepath):
            return {"CANCELLED"}
        mat = _active_mat(context)
        s = mat.pbrqa
        if self.channel in CHANNEL_TYPES:  # added for a chosen channel
            row = s.maps.add()
            row.filepath = self.filepath
            row.guess = detect.classify(self.filepath)[0]
            _assign(s, len(s.maps) - 1, self.channel)
            s.index = len(s.maps) - 1
            build.build(mat)
            return {"FINISHED"}
        t = detect.classify(self.filepath)[0]
        row = s.maps.add()
        row["map_type"] = detect.MAP_IDS.index(t)
        row.filepath = self.filepath
        row.guess = t
        # A new map of a type already in use takes over that channel.
        ch = _channel_of(t)
        if ch:
            for other in s.maps[:-1]:
                if _channel_of(other.map_type) == ch:
                    other["map_type"] = detect.MAP_IDS.index("IGNORE")
        s.index = len(s.maps) - 1
        build.build(mat)
        return {"FINISHED"}


class PBRQA_OT_remove_map(_MatOp, bpy.types.Operator):
    """Remove the selected map from this material (the file on disk is not touched)"""
    bl_idname = "pbrqa.remove_map"
    bl_label = "Remove Map"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        mat = _active_mat(context)
        s = mat.pbrqa
        i = s.index
        if not 0 <= i < len(s.maps):
            return {"CANCELLED"}
        s.maps.remove(i)
        if s.solo_index == i:
            s["solo_index"] = -1
        elif s.solo_index > i:
            s["solo_index"] = s.solo_index - 1
        s.index = min(i, len(s.maps) - 1)
        build.build(mat)
        return {"FINISHED"}


# ---------------------------------------------------------------- channels & layouts
CHANNELS = [  # (id, label, map types that feed it; the first is the default)
    ("BASE_COLOR", "Base Color", ("BASE_COLOR",)),
    ("ROUGHNESS", "Roughness", ("ROUGHNESS", "GLOSS")),
    ("METALLIC", "Metallic", ("METALLIC",)),
    ("NORMAL", "Normal", ("NORMAL_GL", "NORMAL_DX")),
    ("AO", "AO", ("AO",)),
    ("HEIGHT", "Height", ("HEIGHT",)),
    ("BUMP", "Bump", ("BUMP",)),
    ("SPECULAR", "Specular", ("SPECULAR",)),
    ("EMISSION", "Emission", ("EMISSION",)),
    ("OPACITY", "Opacity", ("OPACITY",)),
    ("ARM", "Packed ARM", ("ARM",)),
]
CHANNEL_TYPES = {c[0]: c[2] for c in CHANNELS}


def _channel_of(map_type):
    """Channel id a map type belongs to (Gloss counts as Roughness), or None."""
    for ch, _label, types in CHANNELS:
        if map_type in types:
            return ch
    return None


def _channel_owner(s, ch):
    """(index, item) shown for this channel: exactly the file the material uses
    (same rule as the build); if none is in use, the first unticked or missing one."""
    chosen = build.chosen_maps(s)
    if ch == "ROUGHNESS":  # the build wires Roughness first, Gloss otherwise
        own = chosen.get("ROUGHNESS") or chosen.get("GLOSS")
    else:
        own = chosen.get(build.slot_of(CHANNEL_TYPES[ch][0]))
    if own:
        return own
    for i, it in enumerate(s.maps):
        if it.map_type in CHANNEL_TYPES[ch]:
            return i, it
    return None


def _assign(s, index, ch):
    """Make map `index` the only one feeding channel `ch` (-1: leave it empty)."""
    types = CHANNEL_TYPES[ch]
    for i, it in enumerate(s.maps):
        if i != index and it.map_type in types:
            it["map_type"] = detect.MAP_IDS.index("IGNORE")
    if 0 <= index < len(s.maps):
        it = s.maps[index]
        if it.map_type not in types:
            guess = detect.classify(it.filepath)[0]
            it["map_type"] = detect.MAP_IDS.index(guess if guess in types else types[0])
        it["enabled"] = True


class PBRQA_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    maps_layout: EnumProperty(
        name="Maps Layout",
        items=[("CHANNEL", "By Channel", "One line per material input (Base Color, "
                "Roughness, Normal...) showing the file that feeds it"),
               ("LIST", "Quiet List", "A plain list of files; the selected file's "
                "details sit in one box under it"),
               ("GRID", "Picture Grid", "Big thumbnails; the selected file's details below"),
               ("FULL", "Full List", "Every control on every row (as in version 1.2.0)")],
        default="CHANNEL")
    placement_layout: EnumProperty(
        name="Placement Layout",
        items=[("SIZE_FIRST", "Size First", "Size, Tile Grid, Fit and Reset up front; "
                "projection, rotation and offset folded under More"),
               ("HEADER", "Header Buttons", "Tile Grid and Reset as small icons in the "
                "section header"),
               ("CLASSIC", "Classic", "Projection on top, all main controls visible "
                "(as in version 1.2.0)")],
        default="SIZE_FIRST")

    def draw(self, context):
        col = self.layout.column()
        col.use_property_split = True
        col.prop(self, "maps_layout")
        col.prop(self, "placement_layout")


def _prefs(context):
    try:
        return context.preferences.addons[__package__].preferences
    except (KeyError, AttributeError):
        return None


def _maps_layout(context):
    p = _prefs(context)
    return p.maps_layout if p else "CHANNEL"


def _place_layout(context):
    p = _prefs(context)
    return p.placement_layout if p else "SIZE_FIRST"


class PBRQA_OT_assign_channel(_MatOp, bpy.types.Operator):
    """Use this file for this material input"""
    bl_idname = "pbrqa.assign_channel"
    bl_label = "Use File for Channel"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    channel: StringProperty()
    index: IntProperty(default=-1)

    def execute(self, context):
        if self.channel not in CHANNEL_TYPES:
            return {"CANCELLED"}
        mat = _active_mat(context)
        _assign(mat.pbrqa, self.index, self.channel)
        build.build(mat)
        return {"FINISHED"}


class PBRQA_OT_toggle_variant(_MatOp, bpy.types.Operator):
    """Switch between Roughness and Gloss (white = shiny, gets inverted), or between an
OpenGL and a DirectX normal map (DirectX gets its green flipped)"""
    bl_idname = "pbrqa.toggle_variant"
    bl_label = "Switch Map Variant"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    index: IntProperty(default=-1)

    def execute(self, context):
        mat = _active_mat(context)
        s = mat.pbrqa
        if not 0 <= self.index < len(s.maps):
            return {"CANCELLED"}
        swap = {"ROUGHNESS": "GLOSS", "GLOSS": "ROUGHNESS",
                "NORMAL_GL": "NORMAL_DX", "NORMAL_DX": "NORMAL_GL"}
        it = s.maps[self.index]
        if it.map_type not in swap:
            return {"CANCELLED"}
        it["map_type"] = detect.MAP_IDS.index(swap[it.map_type])
        build.build(mat)
        return {"FINISHED"}


class PBRQA_OT_select_map(_MatOp, bpy.types.Operator):
    """Select this map to see and change its settings below"""
    bl_idname = "pbrqa.select_map"
    bl_label = "Select Map"
    bl_options = {"INTERNAL"}

    index: IntProperty(default=0)

    def execute(self, context):
        _active_mat(context).pbrqa.index = self.index
        return {"FINISHED"}


class PBRQA_OT_toggle_grid(_MatOp, bpy.types.Operator):
    """Lay blue/white squares over the object, one square per tile of the texture.
Switch it off before rendering"""
    bl_idname = "pbrqa.toggle_grid"
    bl_label = "Show Tile Grid"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = _active_mat(context).pbrqa
        s.check_grid = "OFF" if s.check_grid != "OFF" else "TILES"
        return {"FINISHED"}


def _ctx_material(context):
    mat = _active_mat(context)
    return mat if (mat and mat.pbrqa.managed) else None


class PBRQA_MT_channel_files(bpy.types.Menu):
    bl_label = "Choose File"

    def draw(self, context):
        layout = self.layout
        mat = _ctx_material(context)
        ch = getattr(context, "pbrqa_channel", "")
        if mat is None or ch not in CHANNEL_TYPES:
            return
        s = mat.pbrqa
        for i, it in enumerate(s.maps):
            tid = _thumb(it.filepath)
            name = os.path.basename(it.filepath)
            if tid:
                op = layout.operator(PBRQA_OT_assign_channel.bl_idname, text=name, icon_value=tid)
            else:
                op = layout.operator(PBRQA_OT_assign_channel.bl_idname, text=name, icon="IMAGE_DATA")
            op.channel, op.index = ch, i
        layout.separator()
        op = layout.operator(PBRQA_OT_assign_channel.bl_idname, text="None (Don't Use)", icon="X")
        op.channel, op.index = ch, -1
        own = _channel_owner(s, ch)
        if own and ch in ("ROUGHNESS", "NORMAL"):
            i, it = own
            layout.separator()
            on = it.map_type in ("GLOSS", "NORMAL_DX")
            text = "It's a Gloss Map (Invert)" if ch == "ROUGHNESS" else "DirectX Normal (Flip Green)"
            layout.operator(PBRQA_OT_toggle_variant.bl_idname, text=text,
                            icon="CHECKBOX_HLT" if on else "CHECKBOX_DEHLT").index = i
        layout.separator()
        layout.operator_context = "INVOKE_DEFAULT"
        layout.operator(PBRQA_OT_add_map.bl_idname, text="Other File...",
                        icon="FILEBROWSER").channel = ch


class PBRQA_MT_add_channel(bpy.types.Menu):
    bl_label = "Add Map"

    def draw(self, context):
        layout = self.layout
        mat = _ctx_material(context)
        if mat is None:
            return
        layout.operator_context = "INVOKE_DEFAULT"
        free = [c for c in CHANNELS if _channel_owner(mat.pbrqa, c[0]) is None]
        for ch, label, _types in free:
            layout.operator(PBRQA_OT_add_map.bl_idname, text=label + "...").channel = ch
        if not free:
            layout.label(text="Every channel is in use")


class PBRQA_MT_use_as(bpy.types.Menu):
    bl_label = "Use As"

    def draw(self, context):
        layout = self.layout
        try:
            idx = int(getattr(context, "pbrqa_index", "-1"))
        except ValueError:
            return
        for ch, label, _types in CHANNELS:
            op = layout.operator(PBRQA_OT_assign_channel.bl_idname, text=label)
            op.channel, op.index = ch, idx


class PBRQA_MT_maps_specials(bpy.types.Menu):
    bl_label = "Maps"

    def draw(self, context):
        self.layout.operator(PBRQA_OT_rebuild.bl_idname, icon="FILE_REFRESH")


# ---------------------------------------------------------------- drag & drop
class PBRQA_FH_texture_set(bpy.types.FileHandler):
    bl_idname = "PBRQA_FH_texture_set"
    bl_label = "PBR Texture Set"
    bl_import_operator = "pbrqa.load_texture_set"
    bl_file_extensions = ";".join(sorted(detect.IMAGE_EXTS)) + ";.zip"

    @classmethod
    def poll_drop(cls, context):
        area = context.area
        if area is None:
            return False
        if area.type == "NODE_EDITOR":
            return getattr(context.space_data, "tree_type", "") == "ShaderNodeTree"
        return area.type == "VIEW_3D"


# ---------------------------------------------------------------- UI
_previews = None  # thumbnails of the map files (Blender's preview system)


def _thumb(path):
    """Icon id of a small thumbnail of an image file, or 0."""
    if _previews is None or not path or not os.path.isfile(path):
        return 0
    p = _previews.get(path)
    if p is None:
        try:
            p = _previews.load(path, path, "IMAGE")
        except Exception:
            return 0
    return p.icon_id


class PBRQA_UL_maps(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, prop, index=0):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        used = item.enabled and item.map_type != "IGNORE"
        # The sidebar is narrow: thumbnail + type here, the file name shows
        # under the big preview of the selected row.
        sub = row.row(align=True)
        sub.active = used
        if not os.path.isfile(item.filepath):
            sub.label(text="", icon="ERROR")
        else:
            tid = _thumb(item.filepath)
            if tid:
                sub.label(text="", icon_value=tid)
            else:
                sub.label(text="", icon="IMAGE_DATA")
        sub.prop(item, "map_type", text="")
        if hasattr(data, "solo_index"):  # only once it is a material
            on = data.solo_index == index
            op = row.operator(PBRQA_OT_solo_map.bl_idname, text="", emboss=on,
                              icon="SOLO_ON" if on else "SOLO_OFF")
            op.index = index


class PBRQA_UL_maps_quiet(bpy.types.UIList):
    """Tick, picture and type as plain text; details of the selection below."""
    def draw_item(self, context, layout, data, item, icon, active_data, prop, index=0):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        sub = row.row()
        sub.active = item.enabled and item.map_type != "IGNORE"
        text = "Not used" if item.map_type == "IGNORE" else detect.MAP_LABEL[item.map_type]
        tid = _thumb(item.filepath)
        if not os.path.isfile(item.filepath):
            sub.label(text=text, icon="ERROR")
        elif tid:
            sub.label(text=text, icon_value=tid)
        else:
            sub.label(text=text, icon="IMAGE_DATA")


def _row(layout, label="", icon="NONE"):
    """A row with a right-aligned label column, like Blender's own panels.
    A warning icon in front of the label replaces extra hint lines."""
    split = layout.split(factor=0.36)
    lab = split.row()
    lab.alignment = "RIGHT"
    lab.label(text=label, icon=icon)
    return split.row(align=True)


def _note(layout, text, icon="NONE"):
    """A greyed hint line under a control (full width so it isn't cut off)."""
    r = layout.row()
    r.active = False
    r.label(text=text, icon=icon)


OBJ_TYPES = {"MESH", "CURVE", "SURFACE", "META", "FONT"}


def _draw_main(self, context):
    layout = self.layout
    ob = context.active_object
    mat = _active_mat(context)

    # The object's material, with Blender's own name field / browse / new;
    # its slots folded underneath (same widgets as the Material tab).
    if ob is not None and ob.type in OBJ_TYPES:
        layout.template_ID(ob, "active_material", new="material.new")
        header, body = layout.panel("pbrqa_slots", default_closed=True)
        header.label(text="Material Slots (%d)" % len(ob.material_slots))
        if body is not None:
            row = body.row()
            row.template_list("MATERIAL_UL_matslots", "", ob, "material_slots",
                              ob, "active_material_index", rows=3)
            col = row.column(align=True)
            col.operator("object.material_slot_add", icon="ADD", text="")
            col.operator("object.material_slot_remove", icon="REMOVE", text="")
            if ob.mode == "EDIT":
                r = body.row(align=True)
                r.operator("object.material_slot_assign", text="Assign")
                r.operator("object.material_slot_select", text="Select")
                r.operator("object.material_slot_deselect", text="Deselect")

    layout.operator(PBRQA_OT_load.bl_idname, text="Apply Texture Set...", icon="FILEBROWSER")
    pend = context.scene.pbrqa_pending
    if len(pend.maps):
        box = layout.box()
        box.label(text="Found: %s" % (os.path.basename(pend.source.rstrip("\\/")) or "files"),
                  icon="VIEWZOOM")
        box.template_list("PBRQA_UL_maps", "pending", pend, "maps", pend, "index", rows=4)
        row = box.row(align=True)
        row.operator(PBRQA_OT_apply_pending.bl_idname, icon="CHECKMARK")
        row.operator(PBRQA_OT_clear_pending.bl_idname, icon="X", text="")
    if ob is None:
        layout.label(text="Select an object, then apply a set", icon="INFO")
    elif mat is not None and mat.pbrqa.managed and 0 <= mat.pbrqa.solo_index < len(mat.pbrqa.maps):
        box = layout.box()
        r = box.row()
        r.label(text="Showing one map only", icon="SOLO_ON")
        r.operator(PBRQA_OT_solo_map.bl_idname, text="Show All").index = mat.pbrqa.solo_index


class _SubPanel:
    bl_region_type = "UI"
    bl_category = "Texture Tamer"

    @classmethod
    def poll(cls, context):
        mat = _active_mat(context)
        return bool(mat and mat.pbrqa.managed)


def _thumb_label(layout, path, text):
    tid = _thumb(path)
    if not os.path.isfile(path):
        layout.label(text=text, icon="ERROR")
    elif tid:
        layout.label(text=text, icon_value=tid)
    else:
        layout.label(text=text, icon="IMAGE_DATA")


def _solo_button(layout, s, i):
    on = s.solo_index == i
    layout.operator(PBRQA_OT_solo_map.bl_idname, text="", emboss=on,
                    icon="SOLO_ON" if on else "SOLO_OFF").index = i


def _map_detail(layout, s, picture=True, use_tick=False):
    """One box with everything about the selected map."""
    if not 0 <= s.index < len(s.maps):
        return
    i, it = s.index, s.maps[s.index]
    box = layout.box()
    row = box.row()
    if picture:
        tid = _thumb(it.filepath)
        if tid:
            row.column().template_icon(icon_value=tid, scale=3.0)
    col = row.column(align=True)
    col.label(text=os.path.basename(it.filepath),
              icon="NONE" if os.path.isfile(it.filepath) else "ERROR")
    col.prop(it, "map_type", text="")
    if use_tick:
        col.prop(it, "enabled", text="Use This Map")
    on = s.solo_index == i
    col.operator(PBRQA_OT_solo_map.bl_idname, text="Show Only This Map", depress=on,
                 icon="SOLO_ON" if on else "SOLO_OFF").index = i


def _maps_channel(layout, s):
    """B: one line per material input, like Blender's own shader inputs."""
    owned = set()
    col = layout.column()
    for ch, label, _types in CHANNELS:
        own = _channel_owner(s, ch)
        if own is None:
            continue
        i, it = own
        owned.add(i)
        split = col.split(factor=0.4)
        left = split.row(align=True)
        left.prop(it, "enabled", text="")
        lab = left.row()
        lab.active = it.enabled
        name = {"GLOSS": "Gloss", "NORMAL_DX": "Normal DX"}.get(it.map_type, label)
        lab.label(text=name)
        right = split.row(align=True)
        right.active = it.enabled
        right.context_string_set("pbrqa_channel", ch)
        fname = os.path.basename(it.filepath)
        tid = _thumb(it.filepath)
        if not os.path.isfile(it.filepath):
            right.menu("PBRQA_MT_channel_files", text=fname, icon="ERROR")
        elif tid:
            right.menu("PBRQA_MT_channel_files", text=fname, icon_value=tid)
        else:
            right.menu("PBRQA_MT_channel_files", text=fname, icon="IMAGE_DATA")
        _solo_button(right, s, i)
    if not owned:
        col.label(text="No maps in use", icon="INFO")
    layout.menu("PBRQA_MT_add_channel", text="Add Map", icon="ADD")
    unused = [(i, it) for i, it in enumerate(s.maps) if i not in owned]
    if unused:
        header, body = layout.panel("pbrqa_unused", default_closed=True)
        header.label(text="Unused Files (%d)" % len(unused))
        if body is not None:
            for i, it in unused:
                r = body.row(align=True)
                _thumb_label(r, it.filepath, os.path.basename(it.filepath))
                r.context_string_set("pbrqa_index", str(i))
                r.menu("PBRQA_MT_use_as", text="Use As")
                _solo_button(r, s, i)


def _maps_quiet(layout, s):
    """A: plain list, details of the selected file in one box."""
    row = layout.row()
    row.template_list("PBRQA_UL_maps_quiet", "material", s, "maps", s, "index", rows=4)
    col = row.column(align=True)
    col.operator(PBRQA_OT_add_map.bl_idname, icon="ADD", text="")
    col.operator(PBRQA_OT_remove_map.bl_idname, icon="REMOVE", text="")
    col.separator()
    col.menu("PBRQA_MT_maps_specials", icon="DOWNARROW_HLT", text="")
    _map_detail(layout, s, picture=True)


def _maps_grid(layout, s):
    """C: big thumbnails, click a type name to select; details below."""
    flow = layout.grid_flow(row_major=True, columns=3, even_columns=True,
                            even_rows=True, align=False)
    for i, it in enumerate(s.maps):
        col = flow.column(align=True)
        col.active = it.enabled and it.map_type != "IGNORE"
        tid = _thumb(it.filepath)
        if tid:
            col.template_icon(icon_value=tid, scale=3.5)
        else:
            col.label(text="", icon="ERROR" if not os.path.isfile(it.filepath) else "IMAGE_DATA")
        text = "Not used" if it.map_type == "IGNORE" else detect.MAP_LABEL[it.map_type]
        col.operator(PBRQA_OT_select_map.bl_idname, text=text,
                     depress=(i == s.index)).index = i
    r = layout.row(align=True)
    r.operator(PBRQA_OT_add_map.bl_idname, icon="ADD", text="Add")
    r.operator(PBRQA_OT_remove_map.bl_idname, icon="REMOVE", text="Remove")
    r.menu("PBRQA_MT_maps_specials", icon="DOWNARROW_HLT", text="")
    _map_detail(layout, s, picture=False, use_tick=True)


def _maps_full(layout, s):
    """Full list (1.2.0): every control on every row."""
    row = layout.row()
    row.template_list("PBRQA_UL_maps", "material", s, "maps", s, "index", rows=4)
    col = row.column(align=True)
    col.operator(PBRQA_OT_add_map.bl_idname, icon="ADD", text="")
    col.operator(PBRQA_OT_remove_map.bl_idname, icon="REMOVE", text="")
    col.separator()
    col.operator(PBRQA_OT_rebuild.bl_idname, icon="FILE_REFRESH", text="")
    if 0 <= s.index < len(s.maps):
        it = s.maps[s.index]
        tid = _thumb(it.filepath)
        if tid:
            layout.template_icon(icon_value=tid, scale=6.0)
        r = layout.row()
        r.alignment = "CENTER"
        r.active = False
        r.label(text=os.path.basename(it.filepath),
                icon="NONE" if os.path.isfile(it.filepath) else "ERROR")


def _draw_maps(self, context):
    s = _active_mat(context).pbrqa
    mode = _maps_layout(context)
    if mode == "LIST":
        _maps_quiet(self.layout, s)
    elif mode == "GRID":
        _maps_grid(self.layout, s)
    elif mode == "FULL":
        _maps_full(self.layout, s)
    else:
        _maps_channel(self.layout, s)


def _projection_row(layout, s, ob):
    no_uv = (s.projection == "UV" and ob is not None and ob.type == "MESH"
             and not ob.data.uv_layers)  # object has no UV map: say so in the label
    _row(layout, "No UV Map" if no_uv else "Projection",
         "ERROR" if no_uv else "NONE").prop(s, "projection", expand=True)


def _size_rows(layout, s, ob, mat):
    """Size with chain link and presets; Height when unlinked; tiles-fit line."""
    r = _row(layout, "Size" if s.size_linked else "Width")
    r.prop(s, "tile_size", text="")
    r.prop(s, "size_linked", text="", icon="LINKED" if s.size_linked else "UNLINKED")
    r.menu("PBRQA_MT_size_presets", text="", icon="PRESET")
    if not s.size_linked:
        _row(layout, "Height").prop(s, "tile_height", text="")
    if ob is not None and ob.active_material == mat and min(sorted(ob.dimensions)[1:]) > 0:
        d = sorted(ob.dimensions, reverse=True)
        w, h = s.tile_size, build.tile_height(s)
        r = _row(layout)
        sub = r.row()
        sub.active = False
        sub.label(text="%.1f \u00d7 %.1f tiles fit" % (d[0] / w, d[1] / h))
        if s.projection == "UV":
            r.operator(PBRQA_OT_measure.bl_idname, text="", icon="FILE_REFRESH", emboss=False)


def _turn_slide(layout, s):
    r = _row(layout, "Rotation")
    r.prop(s, "rotation", text="")
    r.operator(PBRQA_OT_turn.bl_idname, text="", icon="LOOP_BACK").degrees = 90.0
    r.operator(PBRQA_OT_turn.bl_idname, text="", icon="LOOP_FORWARDS").degrees = -90.0
    col = _row(layout, "Offset").column(align=True)
    col.prop(s, "offset_x", text="X")
    col.prop(s, "offset_y", text="Y")
    if s.projection != "UV" and s.rotation != 0.0:
        _note(layout, "Box/World: turning shows on floors only")


def _hidden_summary(s, projection=True):
    """Short note of changed settings inside a folded section, e.g. 'World, 90°'."""
    parts = []
    if projection and s.projection != "UV":
        parts.append({"BOX": "Box", "WORLD": "World"}[s.projection])
    deg = round(math.degrees(s.rotation)) % 360
    if deg:
        parts.append("%d\u00b0" % deg)
    if s.offset_x or s.offset_y:
        parts.append("Offset")
    return ", ".join(parts)


def _fold_title(text, summary):
    return "%s: %s" % (text, summary) if summary else text


def _fit_reset(layout, reset=True):
    r = layout.row(align=True)
    r.operator(PBRQA_OT_fit.bl_idname)
    if reset:
        r.operator(PBRQA_OT_reset.bl_idname)


def _draw_place(self, context):
    mat = _active_mat(context)
    s = mat.pbrqa
    layout = self.layout
    ob = context.active_object
    sd = context.space_data
    # Textures can't be seen in Solid view: one button fixes it.
    if sd and sd.type == "VIEW_3D" and sd.shading.type in {"SOLID", "WIREFRAME"}:
        layout.operator(PBRQA_OT_material_preview.bl_idname, icon="SHADING_TEXTURE")
    mode = _place_layout(context)
    if mode == "SIZE_FIRST":
        if (s.projection == "UV" and ob is not None and ob.type == "MESH"
                and not ob.data.uv_layers):
            _projection_row(layout, s, ob)  # a problem: show it even when folded
        _size_rows(layout, s, ob, mat)
        on = s.check_grid != "OFF"
        layout.operator(PBRQA_OT_toggle_grid.bl_idname, depress=on, icon="MESH_GRID",
                        text="Show 1 m Grid" if s.check_grid == "METRES" else "Show Tile Grid")
        _fit_reset(layout)
        header, body = layout.panel("pbrqa_more", default_closed=True)
        header.label(text=_fold_title("More", _hidden_summary(s)))
        if body is not None:
            _projection_row(body, s, ob)
            _row(body, "Grid").prop(s, "check_grid", expand=True)
            _turn_slide(body, s)
    elif mode == "HEADER":
        _projection_row(layout, s, ob)
        _size_rows(layout, s, ob, mat)
        _fit_reset(layout, reset=False)
        header, body = layout.panel("pbrqa_turn_slide", default_closed=True)
        header.label(text=_fold_title("Rotation & Offset", _hidden_summary(s, False)))
        if body is not None:
            _row(body, "Grid").prop(s, "check_grid", expand=True)
            _turn_slide(body, s)
    else:  # CLASSIC (1.2.0)
        _projection_row(layout, s, ob)
        _size_rows(layout, s, ob, mat)
        _row(layout, "Check Size").prop(s, "check_grid", expand=True)
        _fit_reset(layout)
        header, body = layout.panel("pbrqa_turn_slide", default_closed=True)
        header.label(text=_fold_title("Rotation & Offset", _hidden_summary(s, False)))
        if body is not None:
            _turn_slide(body, s)


def _place_header(self, context):
    """Header Buttons layout: Tile Grid and Reset at the right of the header."""
    if _place_layout(context) != "HEADER":
        return
    mat = _active_mat(context)
    if not (mat and mat.pbrqa.managed):
        return
    r = self.layout.row(align=True)
    r.operator(PBRQA_OT_toggle_grid.bl_idname, text="", icon="MESH_GRID",
               depress=mat.pbrqa.check_grid != "OFF")
    r.operator(PBRQA_OT_reset.bl_idname, text="", icon="LOOP_BACK")


def _main_header(self, context):
    """Gear: opens this add-on's preferences (layout choices)."""
    op = self.layout.operator("preferences.addon_show", text="", icon="PREFERENCES",
                              emboss=False)
    op.module = __package__


def _draw_repeats(self, context):
    s = _active_mat(context).pbrqa
    layout = self.layout
    r = _row(layout, "Randomise")
    r.prop(s, "random_offset", toggle=True)
    r.prop(s, "random_turn", toggle=True)

    header, body = layout.panel("pbrqa_variation", default_closed=False)
    header.prop(s, "tint_enabled", text="Variation Map")
    if body is None:
        return
    body.active = s.tint_enabled
    if not s.tint_path:
        _row(body).operator(PBRQA_OT_load_tint.bl_idname, icon="IMAGE_DATA")
        return
    r = _row(body, "Image")
    r.label(text=os.path.basename(s.tint_path))
    r.operator(PBRQA_OT_load_tint.bl_idname, text="", icon="FILEBROWSER")
    r.operator(PBRQA_OT_remove_tint.bl_idname, text="", icon="X")
    _row(body, "Size").prop(s, "tint_size", text="")
    _row(body, "Strength").prop(s, "tint_strength", text="")


def _draw_surface(self, context):
    s = _active_mat(context).pbrqa
    col = self.layout.column()
    col.use_property_split = True
    col.use_property_decorate = False
    if s.has_normal:
        col.prop(s, "normal_strength")
    if s.has_bump:
        col.prop(s, "bump_strength")
    if s.has_height:
        col.row().prop(s, "displacement_mode", expand=True)
        if s.displacement_mode != "OFF":
            col.prop(s, "displacement_height")
            col.prop(s, "displacement_midlevel")
        if s.displacement_mode == "REAL":
            col.operator(PBRQA_OT_subdivide.bl_idname, icon="MOD_SUBSURF")
    if s.has_ao:
        col.prop(s, "ao_strength")
    if s.has_emission:
        col.prop(s, "emission_strength")
    if not (s.has_normal or s.has_bump or s.has_height or s.has_ao or s.has_emission):
        col.label(text="No adjustable maps in this set")


def _make_panels(space, suffix):
    def main_poll(cls, context):
        if space == "NODE_EDITOR":
            return getattr(context.space_data, "tree_type", "") == "ShaderNodeTree"
        return True

    main = type("PBRQA_PT_main_" + suffix, (bpy.types.Panel,), {
        "bl_idname": "PBRQA_PT_main_" + suffix, "bl_label": "Texture Tamer",
        "bl_space_type": space, "bl_region_type": "UI", "bl_category": "Texture Tamer",
        "poll": classmethod(main_poll), "draw": _draw_main,
        "draw_header_preset": _main_header})
    subs = []
    for key, label, fn, closed in (("maps", "Maps", _draw_maps, True),
                                   ("place", "Placement", _draw_place, False),
                                   ("repeats", "Break Up Repeats", _draw_repeats, True),
                                   ("surface", "Surface", _draw_surface, False)):
        attrs = {"bl_idname": "PBRQA_PT_%s_%s" % (key, suffix), "bl_label": label,
                 "bl_space_type": space, "bl_parent_id": main.__name__, "draw": fn,
                 "bl_options": {"DEFAULT_CLOSED"} if closed else set()}
        if key == "place":
            attrs["draw_header_preset"] = _place_header
        subs.append(type(attrs["bl_idname"], (_SubPanel, bpy.types.Panel), attrs))
    return [main] + subs


classes = [PBRQA_Preferences, PBRQA_MapItem, PBRQA_Pending, PBRQA_MaterialSettings,
           PBRQA_OT_load, PBRQA_OT_apply_pending, PBRQA_OT_clear_pending,
           PBRQA_OT_rebuild, PBRQA_OT_measure, PBRQA_OT_set_size,
           PBRQA_MT_size_presets, PBRQA_OT_size_preset_add, PBRQA_OT_turn,
           PBRQA_OT_fit, PBRQA_OT_reset, PBRQA_OT_material_preview,
           PBRQA_OT_load_tint, PBRQA_OT_remove_tint, PBRQA_OT_subdivide,
           PBRQA_OT_solo_map, PBRQA_OT_add_map, PBRQA_OT_remove_map,
           PBRQA_OT_assign_channel, PBRQA_OT_toggle_variant, PBRQA_OT_select_map,
           PBRQA_OT_toggle_grid, PBRQA_MT_channel_files, PBRQA_MT_add_channel,
           PBRQA_MT_use_as, PBRQA_MT_maps_specials,
           PBRQA_FH_texture_set, PBRQA_UL_maps, PBRQA_UL_maps_quiet] + \
    _make_panels("VIEW_3D", "view3d") + _make_panels("NODE_EDITOR", "node")


def register():
    global _previews
    _previews = bpy.utils.previews.new()
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Material.pbrqa = PointerProperty(type=PBRQA_MaterialSettings)
    bpy.types.Scene.pbrqa_pending = PointerProperty(type=PBRQA_Pending)


def unregister():
    del bpy.types.Scene.pbrqa_pending
    del bpy.types.Material.pbrqa
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
    global _previews
    if _previews is not None:
        bpy.utils.previews.remove(_previews)
        _previews = None
