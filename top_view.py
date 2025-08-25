import bpy
import math
from mathutils import Vector

# ===== 參數 =====
CAM_NAME        = "TopViewCam"     # 新相機名稱
MAKE_ACTIVE     = True             # 建立後設為目前場景的 active camera
USE_ORTHO       = True             # 使用正交相機；若想用透視改成 False
MARGIN_FACTOR   = 1.05             # Ortho Scale 外擴比例(5%邊界)
Z_OFFSET_MODE   = "auto"           # "auto" 以模型大小自動決定、"fixed" 使用固定數值
Z_OFFSET_VALUE  = 2.0              # 當 Z_OFFSET_MODE = "fixed" 時，距離模型 Zmax 的高度(公尺)

# ===== 複用你前面的設定 =====
ONLY_SELECTED = False # True: 只計算選取物件；False: 計算整個場景 
USE_MODIFIERS = True # True: 考慮 modifiers/deform；False: 只用原始幾何的 bound_box 
INCLUDE_HIDDEN = False # False: 略過在視圖中隱藏的物件

def iter_target_objects():
    objs = bpy.context.selected_objects if ONLY_SELECTED else bpy.context.scene.objects
    for obj in objs:
        if obj.type != 'MESH':
            continue
        if not INCLUDE_HIDDEN and (obj.hide_get() or obj.hide_viewport):
            continue
        yield obj

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

def xyz_extent_from_bound_box_world(obj):
    corners_world = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [c.x for c in corners_world]
    ys = [c.y for c in corners_world]
    zs = [c.z for c in corners_world]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

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

def create_top_view_camera(center_x, center_y, width, height, z_top):
    # 1) 建立或取得相機資料
    cam_data = bpy.data.cameras.new(CAM_NAME)
    cam_obj = bpy.data.objects.new(CAM_NAME, cam_data)
    bpy.context.collection.objects.link(cam_obj)

    # 2) 位置：在中心點上方
    cam_obj.location = (center_x, center_y, z_top)

    # 3) 方向：正上往下看（沿著 -Z）
    cam_obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)

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

# ===== 執行：計算 XYZ 範圍、建立相機 =====
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
