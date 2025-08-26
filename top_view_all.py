import bpy
import os
import math
import json
from datetime import datetime
from mathutils import Vector

# ===== 參數 =====
OUTPUT_PATH     = r"D:\work project\blender-toolBoxForAr"
CAM_NAME        = "TopViewCam"     # 新相機名稱
MAKE_ACTIVE     = True             # 建立後設為目前場景的 active camera
USE_ORTHO       = True             # 使用正交相機；若想用透視改成 False
MARGIN_FACTOR   = 1.05             # Ortho Scale 外擴比例(5%邊界)
Z_OFFSET_MODE   = "fixed"           # "auto" 以模型大小自動決定、"fixed" 使用固定數值
Z_OFFSET_VALUE  = 2.0              # 當 Z_OFFSET_MODE = "fixed" 時，距離模型 Zmax 的高度(公尺)

RENDER_RESOLUTION = 2000           # 輸出解析度，單位：像素

ONLY_SELECTED = False              # True: 只計算選取物件；False: 計算整個場景 
USE_MODIFIERS = True               # True: 考慮 modifiers/deform；False: 只用原始幾何的 bound_box 
INCLUDE_HIDDEN = False             # False: 略過在視圖中隱藏的物件


# ===== 取得場景中要處理的目標物件（根據是否只取選取物件/是否包含隱藏物件） =====
def iter_target_objects():
    objs = bpy.context.selected_objects if ONLY_SELECTED else bpy.context.scene.objects
    for obj in objs:
        if obj.type != 'MESH':
            continue
        if not INCLUDE_HIDDEN and (obj.hide_get() or obj.hide_viewport):
            continue
        yield obj


# ===== 計算物件經過 modifiers/deform 後的 XYZ 範圍（世界座標系下） =====
def xyz_extent_from_evaluated_mesh(obj, depsgraph):
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()
    try:
        if mesh is None or len(mesh.vertices) == 0:
            return None
        mw = eval_obj.matrix_world
        xs, ys, zs = [], [], []
        for v in mesh.vertices:
            wp = mw @ v.co
            xs.append(wp.x); ys.append(wp.y); zs.append(wp.z)
        return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))
    finally:
        eval_obj.to_mesh_clear()


# ===== 計算物件使用 bound_box（未考慮 modifiers）的 XYZ 範圍（世界座標系下） =====
def xyz_extent_from_bound_box_world(obj):
    corners_world = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [c.x for c in corners_world]
    ys = [c.y for c in corners_world]
    zs = [c.z for c in corners_world]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


# ===== 計算整個場景或選取物件的全域 XYZ 範圍（會合併所有物件的 bounding box） =====
def compute_global_xyz_extents():
    depsgraph = bpy.context.evaluated_depsgraph_get() if USE_MODIFIERS else None

    min_x = math.inf; max_x = -math.inf
    min_y = math.inf; max_y = -math.inf
    min_z = math.inf; max_z = -math.inf
    count = 0

    for obj in iter_target_objects():
        if USE_MODIFIERS:
            ext = xyz_extent_from_evaluated_mesh(obj, depsgraph)
            if ext is None:
                continue
        else:
            if not obj.data or not hasattr(obj.data, "vertices") or len(obj.data.vertices) == 0:
                continue
            ext = xyz_extent_from_bound_box_world(obj)

        oxmin, oxmax, oymin, oymax, ozmin, ozmax = ext
        min_x = min(min_x, oxmin); max_x = max(max_x, oxmax)
        min_y = min(min_y, oymin); max_y = max(max_y, oymax)
        min_z = min(min_z, ozmin); max_z = max(max_z, ozmax)
        count += 1

    if count == 0:
        print("[Info] 沒有符合條件的物件（可能沒有 MESH、全都隱藏，或沒有幾何）")
        return None

    return (min_x, max_x, min_y, max_y, min_z, max_z, count)


# ===== 建立一台新的相機，從正上方看下來，並設定為正交或透視 =====
def create_top_view_camera(center_x, center_y, width, height, z_top):
    # 1) 建立或取得相機資料
    cam_data = bpy.data.cameras.new(CAM_NAME)
    cam_obj = bpy.data.objects.new(CAM_NAME, cam_data)
    bpy.context.collection.objects.link(cam_obj)

    # 2) 位置：在中心點上方
    cam_obj.location = (center_x, center_y, z_top)

    # 3) 方向：正上往下看（沿著 -Z）
    cam_obj.rotation_euler = (0.0, 0.0, 0.0)

    # 4) 設為正交/透視與視野
    if USE_ORTHO:
        cam_data.type = 'ORTHO'
        # Ortho Scale 用較長邊，外加邊界
        ortho_scale = max(width, height) * MARGIN_FACTOR
        cam_data.ortho_scale = ortho_scale
    else:
        cam_data.type = 'PERSP'
        cam_data.lens = 50.0  # mm，可自行調整
        # 透視相機的高度需要能包住畫面，這裡簡單選一個保守高度：
        # 你已經把 z_top 設在模型上方，若需要更嚴謹，可用三角關係由 FOV 推回距離

    # 5) 設為場景 active camera（可選）
    if MAKE_ACTIVE:
        bpy.context.scene.camera = cam_obj

    print(f"✔ 已建立相機 '{CAM_NAME}'，位置=({cam_obj.location.x:.3f}, {cam_obj.location.y:.3f}, {cam_obj.location.z:.3f})")
    return cam_obj


# ===== 渲染 =====
def set_viewport_shading(area):
    # 設定 Viewport Shading（亮白＋黑輪廓）
    sh = area.spaces.active.shading
    sh.type = 'SOLID'
    sh.light = 'FLAT'
    sh.color_type = 'SINGLE'
    sh.single_color = (1,1,1)            # 物件白
    sh.background_type = 'VIEWPORT'
    sh.background_color = (1,1,1)        # 背景白
    sh.show_object_outline = True
    sh.object_outline_color = (0,0,0)    # 黑外框
    sh.show_cavity = True
    sh.cavity_type = 'BOTH'
    sh.cavity_ridge_factor = 1.2
    sh.cavity_valley_factor = 1.2
    sh.show_xray = False
    sh.show_shadows = False


# ===== 相機設定 =====
def set_render_settings(scn, width, height, engine='BLENDER_WORKBENCH'):
    scn.render.engine = engine  # Workbench 渲染引擎
    scn.view_settings.view_transform = 'Standard'
    scn.view_settings.look = 'High Contrast'
    # 根據比例調整解析度，最大值為2000
    if width >= height:
        res_x = RENDER_RESOLUTION
        res_y = int(RENDER_RESOLUTION * height / width)
        scale = width / RENDER_RESOLUTION
    else:
        res_y = RENDER_RESOLUTION
        res_x = int(RENDER_RESOLUTION * width / height)
        scale = height / RENDER_RESOLUTION
    scn.render.resolution_x = res_x
    scn.render.resolution_y = res_y
    scn.render.resolution_percentage = 100  # 100% 輸出，不縮放

    # 回傳像素對應實際長寬的比例
    return scale

# ===== 依據 Blender 場景單位自動換算成公分 =====
def to_centimeters(value, unit):
    if unit == 'METERS':
        return value * 100
    elif unit == 'CENTIMETERS':
        return value
    elif unit == 'MILLIMETERS':
        return value / 10
    elif unit == 'KILOMETERS':
        return value * 100000
    elif unit == 'INCHES':
        return value * 2.54
    elif unit == 'FEET':
        return value * 30.48
    else:  # Blender Unit 或未知
        return value * 100  # 假設 1BU=1m




# ===== 執行：計算 XYZ 範圍、建立相機 =====
def main():
    ext = compute_global_xyz_extents()
    if ext:
        min_x, max_x, min_y, max_y, min_z, max_z, n = ext
        center_x = 0.5 * (min_x + max_x)
        center_y = 0.5 * (min_y + max_y)
        width    = max_x - min_x
        height   = max_y - min_y

        # 自動決定相機離物件頂端高度（正交相機其實高度不影響取景，但留一點安全距離）
        if Z_OFFSET_MODE == "auto":
            # 用最大邊的 0.5 作為高度緩衝，避免太貼近（你也可以改為 0.2、1.0 等）
            z_top = max_z + max(width, height) * 0.5
        else:
            z_top = max_z + float(Z_OFFSET_VALUE)

        create_top_view_camera(center_x, center_y, width, height, z_top)
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

    length_unit = bpy.context.scene.unit_settings.length_unit
    width_cm         = to_centimeters(width, length_unit)
    height_cm        = to_centimeters(height, length_unit)
    scn = bpy.context.scene
    scale = set_render_settings(scn, width_cm, height_cm)
    ts = datetime.now().strftime("%m%d%H%M")
    scn.render.filepath = os.path.join(OUTPUT_PATH, f"top_view{ts}.png").replace("\\","/")
    bpy.ops.render.render(write_still=True)
    print("Saved:", scn.render.filepath)

    # 匯出尺寸資訊
    size_txt_path = os.path.join(OUTPUT_PATH, f"top_view_size{ts}.txt").replace("\\","/")
    actual_width  = scn.render.resolution_x * scale
    actual_height = scn.render.resolution_y * scale

    with open(size_txt_path, "w", encoding="utf-8") as f:
        f.write(f"解析度(像素)\n{scn.render.resolution_x} x {scn.render.resolution_y}\n")
        f.write(f"實際長寬_相片(cm)\n{actual_width*MARGIN_FACTOR:.4f} x {actual_height*MARGIN_FACTOR:.4f}\n")
        f.write(f"實際長寬(cm)\n{width_cm*MARGIN_FACTOR:.4f} x {height_cm*MARGIN_FACTOR:.4f}\n")
        f.write(f"像素對應實際長寬的比例(cm/px)\n{scale:.4f}\n")
    print("Saved:", size_txt_path)

    
if __name__ == "__main__":
    main()