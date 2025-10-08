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
Z_OFFSET_VALUE  = 2.0              # 當 Z_OFFSET_MODE = "fixed" 時，距離模型 Zmax 的高度(公尺) [負數表示在模型內部]

RENDER_RESOLUTION = 2000           # 輸出解析度，單位：像素
RENDER_RESOLUTION_X = 1920           # 輸出解析度，單位：像素
RENDER_RESOLUTION_Y = 1080           # 輸出解析度，單位：像素

ONLY_SELECTED = False              # True: 只計算選取物件；False: 計算整個場景 
USE_MODIFIERS = True               # True: 考慮 modifiers/deform；False: 只用原始幾何的 bound_box 
INCLUDE_HIDDEN = False             # False: 略過在視圖中隱藏的物件

ADD_ORIGIN_CONE = True                  # True: 在 (0,0) 放一個錐體； False: 不放錐體
ORIGIN_CONE_SIZE = 45                   # 錐體大小，單位：Pixel
ORIGIN_CONE_NAME = "OriginCone"         # 原點指示錐體名稱
ORIGIN_CONE_Z_MODE = "auto_top"         # "auto_top": 放在模型頂端上方、"zero": 放在 Z=0
ORIGIN_CONE_Z_OFFSET = 0.1              # 當 ORIGIN_CONE_Z_MODE = "auto_top" 時，錐體離模型頂端的高度  [負數表示在模型內部 約Z_OFFSET_VALUE+0.5]
DELETE_ORIGIN_CONE_AFTER_RENDER = True  # True: 渲染後刪除錐體； False: 渲染後保留錐體
ORIGIN_CONE_DIRECTION = "+y"            # 錐體頂端面向 : 可選 "+x"(90), "-x"(-90), "+y"(180), "-y"(0)
ORIGIN_CONE_VIEW_COLOR = (1.0, 0.0, 0.0, 1.0) # 錐體顏色 (R,G,B,A)，紅色


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
        check_x = width / RENDER_RESOLUTION_X
        check_y = height / RENDER_RESOLUTION_Y
        if RENDER_RESOLUTION_X >= RENDER_RESOLUTION_Y:
            if check_x >= check_y:
                ortho_scale = width * MARGIN_FACTOR
            else:
                ortho_scale = check_y * RENDER_RESOLUTION_X * MARGIN_FACTOR
        else:
            if check_x >= check_y:
                ortho_scale = check_x * RENDER_RESOLUTION_Y * MARGIN_FACTOR
            else:
                ortho_scale = height * MARGIN_FACTOR
        
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
    check_x = width / RENDER_RESOLUTION_X
    check_y = height / RENDER_RESOLUTION_Y
    # 根據比例調整解析度，最大值為2000
    if check_x >= check_y:
        # res_x = RENDER_RESOLUTION_X
        # res_y = int(RENDER_RESOLUTION_Y * height / width)
        scale = width * MARGIN_FACTOR / RENDER_RESOLUTION_X
    else:
        # res_y = RENDER_RESOLUTION_Y
        # res_x = int(RENDER_RESOLUTION_X * width / height)
        scale = height * MARGIN_FACTOR / RENDER_RESOLUTION_Y
    scn.render.resolution_x = RENDER_RESOLUTION_X
    scn.render.resolution_y = RENDER_RESOLUTION_Y
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

# ===== 取得 .blend 檔所在資料夾 =====
def get_base_dir():
    if bpy.data.filepath:                     # 有存檔
        return bpy.path.abspath("//")
    # 尚未存檔時，退回到暫存或使用者家目錄
    return bpy.app.tempdir or os.path.expanduser("~") + os.sep

# 取得 .blend 檔名（不含副檔名）
def get_blend_stem():
    if bpy.data.filepath:
        return bpy.path.display_name_from_filepath(bpy.data.filepath)
    return "untitled"

# ===== 建立與刪除原點指示錐體 =====
def create_origin_cone(cone_size, z_pos):
    # 先確保同名物件不存在
    old = bpy.data.objects.get(ORIGIN_CONE_NAME)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)

    # 依據 ORIGIN_CONE_DIRECTION 設定 rotationZ
    dir_map = {
        "+x":  90,
        "-x": -90,
        "+y": 180,
        "-y":   0
    }
    rot_z_deg = dir_map.get(ORIGIN_CONE_DIRECTION, 0)  # 預設 0

    bpy.ops.mesh.primitive_cone_add(
        vertices=3,
        radius1=cone_size/2,
        radius2=0.0,
        depth=cone_size,
        enter_editmode=False,
        align='WORLD',
        location=(0.0, 0.0, z_pos),
        rotation=(math.radians(90), 0.0, math.radians(rot_z_deg))
    )
    cone = bpy.context.active_object
    cone.name = ORIGIN_CONE_NAME

    # === 建立材質並設定顏色 ===
    mat_name = ORIGIN_CONE_NAME + "_Mat"
    mat = bpy.data.materials.get(mat_name) or bpy.data.materials.new(mat_name)
    mat.use_nodes = False                     # 關閉節點
    mat.diffuse_color = ORIGIN_CONE_VIEW_COLOR  # 對應 Viewport Display > Color
    # mat.use_nodes = True
    # bsdf = mat.node_tree.nodes.get("Principled BSDF")
    # if bsdf:
    #     bsdf.inputs["Base Color"].default_value = ORIGIN_CONE_COLOR
    # 指派材質給錐體
    if len(cone.data.materials) == 0:
        cone.data.materials.append(mat)
    else:
        cone.data.materials[0] = mat

    return cone

def delete_origin_cone():
    cone = bpy.data.objects.get(ORIGIN_CONE_NAME)
    if cone:
        bpy.data.objects.remove(cone, do_unlink=True)


# ===== 執行：計算 XYZ 範圍、建立相機 =====
def main():
    # 取得 .blend 檔所在資料夾（"//" 代表 .blend 的目錄）
    base_dir   = get_base_dir()                   # e.g. C:\Users\User\Desktop\folderA\
    blend_stem = get_blend_stem()                 # e.g. filename

    # 目標資料夾：<base_dir>\<blend_stem>\
    OUTPUT_PATH = bpy.path.abspath(f"//{blend_stem}") if bpy.data.filepath else os.path.join(base_dir, blend_stem)
    os.makedirs(OUTPUT_PATH, exist_ok=True)

    # 目標檔案：<base_dir>\<blend_stem>\<blend_stem>.txt
    size_json_path = os.path.join(OUTPUT_PATH, f"{blend_stem}.txt").replace("\\", "/")
    
    # 計算 XYZ 範圍
    ext = compute_global_xyz_extents()
    if not ext:
        print("✘ 無法建立相機（沒有幾何範圍）。")
        return
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
    
    # 設定並執行渲染
    area  = next((a for a in bpy.context.screen.areas if a.type == 'VIEW_3D'), None)
    if not area:
        raise RuntimeError("找不到 VIEW_3D 視窗")
    region = next((r for r in area.regions if r.type == 'WINDOW'), None)
    if not region:
        raise RuntimeError("在 VIEW_3D 中找不到 WINDOW region。")
    set_viewport_shading(area)

    # 內部運算使用meters
    length_unit = 'METERS'
    # length_unit = bpy.context.scene.unit_settings.length_unit
    width_cm         = to_centimeters(width, length_unit)
    height_cm        = to_centimeters(height, length_unit)
    scn = bpy.context.scene
    scale = set_render_settings(scn, width_cm, height_cm)

    cone_size = ORIGIN_CONE_SIZE / 100 * scale
    # 在截圖前於 (0,0) 放一個錐體（不影響邊界計算，因為放在這之後才建立）
    if ADD_ORIGIN_CONE:
        if ORIGIN_CONE_Z_MODE == "auto_top":
            cone_z = max_z + ORIGIN_CONE_Z_OFFSET
        else:  # "zero"
            cone_z = 0.0
        cone_obj = create_origin_cone(cone_size, cone_z)

    ts = datetime.now().strftime("%m%d%H%M")
    # scn.render.filepath = os.path.join(OUTPUT_PATH, f"top_view{ts}.png").replace("\\","/")
    scn.render.filepath = os.path.join(OUTPUT_PATH, f"MF.png").replace("\\","/")
    bpy.ops.render.render(write_still=True)
    print("Saved:", scn.render.filepath)

    # 匯出尺寸資訊
    # 目標檔案：<base_dir>\<blend_stem>\<blend_stem>.json
    size_json_path = os.path.join(OUTPUT_PATH, f"{blend_stem}.json").replace("\\", "/")
    # size_json_path = os.path.join(OUTPUT_PATH, f"top_view_size{ts}.json").replace("\\","/")
    actual_width  = scn.render.resolution_x * scale
    actual_height = scn.render.resolution_y * scale

    # === 計算 Blender 世界原點 (0,0,0) 在輸出圖片中的像素與比例位置 ===
    cam_obj = scn.camera
    if cam_obj is None or cam_obj.type != 'CAMERA':
        raise RuntimeError("找不到有效的場景相機，無法計算原點在影像中的位置。")

    cam_data = cam_obj.data
    res_x = scn.render.resolution_x
    res_y = scn.render.resolution_y

    # 正交相機：水平/垂直視野（世界單位）
    # 注意：此公式假設相機垂直於 XY（你的程式就是這樣設的）
    if cam_data.type != 'ORTHO':
        raise RuntimeError("目前相機不是 ORTHO，原點→像素的快速公式不適用。")

    if RENDER_RESOLUTION_X >= RENDER_RESOLUTION_Y:
        Sx = cam_data.ortho_scale
        Sy = Sx * (res_y / res_x)
    else:
        Sy = cam_data.ortho_scale
        Sx = Sy * (res_x / res_y)

    # 你的相機中心就是 (center_x, center_y)
    # center_x/center_y 已在上面計算出來（包圍盒中心）
    x0, y0 = 0.0, 0.0

    # 世界 -> 像素（左下角為 (0,0)）
    px = ((x0 - center_x) / Sx + 0.5) * res_x
    py = ((y0 - center_y) / Sy + 0.5) * res_y

    # 比例（0~1），可用來判斷在圖片中的相對位置
    rx = px / res_x
    ry = py / res_y

    output_dict = {
        "render_resolution": {
            "unit": "px",
            "width": res_x,
            "height": res_y
        },
        "model_dimensions": [
            {
                "unit": "cm",
                "width": width_cm,
                "height": height_cm
            },
            {
                "unit": "m",
                "width": width_cm / 100,
                "height": height_cm / 100
            }
        ],
        "actual_dimensions_photo": [
            {
                "unit": "cm",
                "width": actual_width,
                "height": actual_height
            },
            {
                "unit": "m",
                "width": actual_width / 100,
                "height": actual_height / 100
            }
        ],
        "actual_dimensions_view-for_check": [
            {
                "unit": "cm",
                "width": width_cm,
                "height": height_cm
            },
            {
                "unit": "m",
                "width": width_cm / 100,
                "height": height_cm / 100
            }
        ],
        "pixel_to_actual_dimensions_ratio": [
            {
                "unit": "cm/px",
                "ratio": scale
            },
            {
                "unit": "m/px",
                "ratio": scale / 100
            },
            {
                "unit": "PX/m",
                "ratio": 1 / (scale / 100)
            }
        ],
        "origin_in_image": {
            "pixel": [
                {"start-at":"左下", "x": round(px, 2), "y": round(py, 2)},
                {"start-at":"左上", "x": round(px, 2), "y": round(res_y-py, 2)},
            ],
            "ratio": [
                {"start-at":"左下", "x": rx, "y": ry},             # 0~1，(0,0)=左下、(1,1)=右上
                {"start-at":"左上", "x": rx, "y": 1-ry},           # 0~1，(0,0)=左上、(1,1)=右下
            ]
        }
    }

    with open(size_json_path, "w", encoding="utf-8") as f:
        json.dump(output_dict, f, ensure_ascii=False, indent=4)
    print("Saved:", size_json_path)

    # 渲染和輸出完成後刪除臨時相機
    cam_obj = bpy.data.objects.get(CAM_NAME)
    if cam_obj:
        bpy.data.objects.remove(cam_obj, do_unlink=True)
        cam_data = bpy.data.cameras.get(CAM_NAME)
        if cam_data:
            bpy.data.cameras.remove(cam_data, do_unlink=True)
        print(f"✔ 已刪除臨時相機 '{CAM_NAME}'")
    
    # (可選）刪除錐體與臨時相機
    cone_obj = bpy.data.objects.get(ORIGIN_CONE_NAME)
    if DELETE_ORIGIN_CONE_AFTER_RENDER and cone_obj:
        bpy.data.objects.remove(cone_obj, do_unlink=True)

    
if __name__ == "__main__":
    main()