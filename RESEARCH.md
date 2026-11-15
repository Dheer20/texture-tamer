# Research notes (14 Nov 2026)

What Blender already offers, what the texture sites call their maps, and why the
add-on is built the way it is. Sources are linked; anything not checked is marked.

## Blender's own tools

| Tool | What it does | What it leaves out | Source |
|---|---|---|---|
| Node Wrangler "Add Principled Setup" (Ctrl+Shift+T), ships with Blender 5.3 in `scripts/addons_core/node_wrangler` | Picks files by name tags, adds image nodes, sets colour space, wires them to a Principled BSDF. Gloss gets an Invert node. | Read in the 5.3 source (`operators/add_principled_setup.py`): no DirectX green flip, no packed ARM/ORM split, AO is loaded but **not connected**, true displacement left as a TODO ("Too complicated for now"), no tile-size/strength controls afterwards, no zip, no drag-and-drop. | [Manual](https://docs.blender.org/manual/en/latest/addons/node/node_wrangler.html), tag case issue [#104693](https://projects.blender.org/blender/blender-addons/issues/104693), local source |
| Extensions format (`blender_manifest.toml`, `schema_version = "1.0.0"`, `[permissions] files = "..."`, `blender --command extension build/validate`) | The official way to package an add-on since 4.2. Used here. | - | [How to Create Extensions](https://docs.blender.org/manual/en/latest/advanced/extensions/getting_started.html) |
| `bpy.types.FileHandler` with `poll_drop` | Official drag-and-drop from the OS into an editor. Used here for the 3D Viewport and Shader Editor. | - | [API 5.3](https://docs.blender.org/api/5.3/bpy.types.FileHandler.html), [PR #116047](https://projects.blender.org/blender/blender/pulls/116047) |
| Material setting Displacement = "Displacement and Bump" (`displacement_method = 'BOTH'`) | Real displacement plus bump from one height map. Used here instead of hand-building a second bump. | Needs enough geometry; the panel offers a Simple Subdivision button. | Checked in Blender 5.3 Python: values `BUMP`, `DISPLACEMENT`, `BOTH` |
| Asset Browser | Good for *storing* finished materials. | Does not build a material from loose files. Not used. | Not re-checked this session |

Decision: Node Wrangler is not called, because the cases the brief asks for (DirectX,
ARM, AO multiply, displacement, controls, zip, drop) are exactly the ones it leaves out.
The add-on copies its splitting idea (separators + CamelCase) and its built-in nodes
(Image Texture, Invert, Normal Map, Bump, Displacement, Mapping), and adds the rest.

## How the sites name their maps

| Site | Example names | Source |
|---|---|---|
| ambientCG | `Bricks076C_2K-PNG_Color`, `_NormalGL`, `_NormalDX`, `_Roughness`, `_Displacement`, `_AmbientOcclusion`, `_Metalness`, `_Opacity` | Secondary only: [importer regexes](https://gist.github.com/Wampa842/59aa27a13f71d6a3c78dc4ca71c83712), [s&box wiki](https://wiki.facepunch.com/sbox/Material_Resources~diff:547044). No official naming page found. |
| Poly Haven | `diff`, `nor_gl`, `nor_dx`, `rough`, `metal`, `disp`, `ao`, `arm` (R=AO, G=rough, B=metal) | [Poly Haven texture standards](https://docs.polyhaven.com/en/technical-standards/textures) |
| Poliigon | older: `COL`, `NRM`, `GLOSS`, `REFL`, `DISP` (16-bit), `AO`, `METALNESS`; newer: Pascal Case | [Texture maps explained](https://help.poliigon.com/en/articles/1712652-texture-maps-explained), [2024 standards](https://www.blog.poliigon.com/blog/2024-texture-standards) |
| FreePBR | `brick-wall_albedo`, `_ao`, `_height`, `_metallic`, `_normal-ogl`, `_roughness`, `_preview` | Forum listing only: [outerspace-software](https://www.outerspace-software.com/community/15345/free-pbr-textures-to-use-with-pbr-cfx), [80.lv](https://80.lv/articles/a-collection-of-free-pbr-materials) |
| Quixel / Megascans | `Albedo`, `Normal`, `Roughness`, `Displacement`, `AO`, `Cavity`, `Gloss`, `Specular`, `Translucency`, `Opacity`, `Bump` | **Not confirmed** from an official page; names taken from common downloads. |
| Textures.com | **Could not check** (no page found). Covered by the general words (albedo, normal, roughness, height, metallic). | - |
| ORM / ARM packing | R = occlusion, G = roughness, B = metallic | [aitextured](https://aitextured.com/articles/download_pbr_textures_in_zip_archives_new_feature_on_aitextured.html), Poly Haven above |

Colour spaces: Poliigon states colour (COL) and reflection maps are sRGB and 16-bit DISP
is linear; everything except colour and emission is set to Non-Color here.
OpenGL vs DirectX: Blender uses OpenGL (Y+) normals; DirectX ones need the green
channel flipped ([s&box wiki](https://wiki.facepunch.com/sbox/Material_Resources~diff:547044), Poly Haven standards above).
