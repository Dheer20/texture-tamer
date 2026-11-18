# Changelog

## Unreleased
- Sets with several emission maps (e.g. `x_emission`, `x_emission_all_on`, `x_emission_dim`):
  the plain `x_emission` is used, not whichever file is biggest. The variants stay in the
  list as unused files, so you can switch to one.
- The set's JSON can give a starting **Emission Strength**: `"emission_strength_hint": 20`
  (a number above 0). Without it the strength still starts at 1.

## 1.3.1
- One rule in every Maps layout: each material input takes one file. Giving a file a
  type (in any layout, or in the check-first list) takes that job over; the previous
  file becomes unused. A set with both a roughness and a gloss map uses the roughness.
- By Channel always shows the file the material really uses (also for older materials).
- Folded sections name changed settings they hide, e.g. "More: World, 90°".

## 1.3.0
- Layout choices in Preferences (gear icon in the panel header):
  Maps as **By Channel** (default), Quiet List, Picture Grid or Full List;
  Placement as **Size First** (default), Header Buttons or Classic.
- By Channel: one line per material input with its file; pick another file, set a
  channel to None, switch Gloss/Roughness and DirectX/OpenGL from the file menu;
  "Add Map" for empty channels; leftover files under "Unused Files".
- Size First: Show Tile Grid button; projection, rotation, offset folded under "More".

## 1.2.0
- Renamed from "PBR Quick Apply" to **Texture Tamer**.
- Maps: use/skip tick box, thumbnails, "show only this map", add/remove files.
- Displacement Off by default (Off / Bump / Real); depth and midlevel read from the
  set's JSON file when present.
- Material name field and Material Slots list in the panel.

## 1.1.0 – 1.1.1
- Placement: real-world size with presets, size read from the set's JSON, tile grid and
  1 m grid, Fit to Object, World projection, rotation/offset, random shift/turn per
  object, variation map found next to the set. Calmer layout in 1.1.1.

## 1.0.0
- Folder / zip / single image / drag-and-drop to a finished Principled BSDF material;
  messy-name detection; DirectX normals, gloss, packed ARM, 16-bit height, emission.
