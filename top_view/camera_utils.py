import bpy
import math
from mathutils import Vector

def iter_target_objects(only_selected, include_hidden):
    objs = bpy.context.selected_objects if only_selected else bpy.context.scene.objects
    for obj in objs:
        if obj.type != 'MESH':
            continue
        if not include_hidden and (obj.hide_get() or obj.hide_viewport):
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
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)

def compute_global_xyz_extents(only_selected, use_modifiers, include_hidden):
    depsgraph = bpy.context.evaluated_depsgraph_get() if use_modifiers else None
    min_x = math.inf; max_x = -math.inf
    min_y = math.inf; max_y = -math.inf
    min_z = math.inf; max_z = -math.inf
    count = 0
    for obj in iter_target_objects(only_selected, include_hidden):
        if use_modifiers:
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
        print("[Info] 沒有符合條件的物件")
        return None
    return (min_x, max_x, min_y, max_y, min_z, max_z, count)

def create_top_view_camera(center_x, center_y, width, height, z_top, cam_name, use_ortho, margin_factor, make_active):
    cam_data = bpy.data.cameras.new(cam_name)
    cam_obj = bpy.data.objects.new(cam_name, cam_data)
    bpy.context.collection.objects.link(cam_obj)
    cam_obj.location = (center_x, center_y, z_top)
    cam_obj.rotation_euler = (0.0, 0.0, 0.0)
    if use_ortho:
        cam_data.type = 'ORTHO'
        ortho_scale = max(width, height) * margin_factor
        cam_data.ortho_scale = ortho_scale
    else:
        cam_data.type = 'PERSP'
        cam_data.lens = 50.0
    if make_active:
        bpy.context.scene.camera = cam_obj
    print(f"✔ 已建立相機 '{cam_name}'，位置=({cam_obj.location.x:.3f}, {cam_obj.location.y:.3f}, {cam_obj.location.z:.3f})")
    return cam_obj