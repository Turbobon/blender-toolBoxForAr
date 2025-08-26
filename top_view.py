import bpy
import os
from datetime import datetime
from camera_utils import compute_global_xyz_extents, create_top_view_camera
from render_utils import set_viewport_shading, set_render_settings

# ===== 參數 =====
CAM_NAME        = "TopViewCam"
MAKE_ACTIVE     = True
USE_ORTHO       = True
MARGIN_FACTOR   = 1.05
Z_OFFSET_MODE   = "fixed"
Z_OFFSET_VALUE  = 2.0
ONLY_SELECTED   = False
USE_MODIFIERS   = True
INCLUDE_HIDDEN  = True

def main():
    ext = compute_global_xyz_extents(ONLY_SELECTED, USE_MODIFIERS, INCLUDE_HIDDEN)
    if ext:
        min_x, max_x, min_y, max_y, min_z, max_z, n = ext
        center_x = 0.5 * (min_x + max_x)
        center_y = 0.5 * (min_y + max_y)
        width    = max_x - min_x
        height   = max_y - min_y
        if Z_OFFSET_MODE == "auto":
            z_top = max_z + max(width, height) * 0.5
        else:
            z_top = max_z + float(Z_OFFSET_VALUE)
        create_top_view_camera(center_x, center_y, width, height, z_top,
                              CAM_NAME, USE_ORTHO, MARGIN_FACTOR, MAKE_ACTIVE)
    else:
        print("✘ 無法建立相機（沒有幾何範圍）。")
        return

    area  = next((a for a in bpy.context.screen.areas if a.type == 'VIEW_3D'), None)
    if not area:
        raise RuntimeError("找不到 VIEW_3D 視窗")
    region = next((r for r in area.regions if r.type == 'WINDOW'), None)
    if not region:
        raise RuntimeError("在 VIEW_3D 中找不到 WINDOW region。")
    set_viewport_shading(area)

    scn = bpy.context.scene
    set_render_settings(scn, 2000, 2000)
    ts = datetime.now().strftime("%m%d%H%M")
    scn.render.filepath = os.path.join(r"C:\Users\User\Desktop", f"top_view{ts}.png").replace("\\","/")
    bpy.ops.render.render(write_still=True)
    print("Saved:", scn.render.filepath)

if __name__ == "__main__":
    main()