# Blender Tool Box for AR

Blender Tool Box for AR is a collection of Blender add-ons and scripts that streamline preparing models for augmented reality. It targets Blender 2.80+ and provides tools for mesh cleanup, IFC processing, exporting and top view rendering.

## Features

- **Z-axis rotation** – quickly rotate selected meshes or the whole scene around the Z axis.
- **IFC ElementId renaming** – rename elements in an IFC using their `Tag` values, with single-file and batch processing support.
- **Utility operations** – rename mesh data to match object names, assign default materials, set materials to `BLEND`, move models to the scene origin and cut meshes along an axis.
- **Model export** – export the current blend file to glTF (`.gltf`), GLB and USDZ formats and bundle the glTF output into a ZIP archive.
- **Top view capture** – create a camera above the scene, render a top-down image and generate JSON with pixel-to-real-world size ratios.

## Requirements

- [Blender](https://www.blender.org) 2.80 or newer.
- Optional: [`ifcopenshell`](https://github.com/IfcOpenShell/IfcOpenShell) for IFC renaming features.

## Installation

1. In Blender, go to **Edit ▸ Preferences ▸ Add-ons**.
2. Click **Install…** and choose `ar_tool_box.py`.
3. Enable the **AR Tool Box** add-on.

## Usage

The add-on adds an **AR Tool Box** panel in the 3D Viewport Sidebar with the tools listed above. The repository also contains standalone scripts:

- `top_view.py` – renders a top view PNG of the scene.
- `top_view_all.py` – renders a top view PNG and writes size information to JSON.

Run these scripts within Blender's scripting workspace or with Blender's Python in background mode.

## Directory Structure

```
ar_tool_box.py   # main add-on
camera_utils.py  # camera helpers used by top view scripts
render_utils.py  # rendering helpers
top_view.py      # create and save a top view image
top_view_all.py  # extended top view renderer with size metadata
```

## Contributing

Issues and pull requests are welcome.
