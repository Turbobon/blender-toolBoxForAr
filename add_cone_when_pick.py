bl_info = {
    "name": "QR Cone Tool",
    "author": "ChatGPT + SUNG",
    "version": (1, 3, 0),
    "blender": (4, 0, 0),
    "location": "View3D > N panel > QR Cones",
    "description": "Place cones with fixed rotations, edit them, and export to JSON",
    "category": "Object",
}

import bpy
import math
import json
from bpy.props import (
    EnumProperty,
    BoolProperty,
)
from bpy_extras import view3d_utils
from bpy_extras.io_utils import ExportHelper
import mathutils

# ------------------------------------------------------------------------
# Constants & helpers
# ------------------------------------------------------------------------

# Name of collection for QR cones
QR_COLLECTION_NAME = "QR_Cones"

# Face value to rotation mapping (degrees)
# key: dropdown value (1~4), value: rotation Z in degrees
FACE_ROTATIONS_DEG = {
    1: 180.0,    # up
    2: 90.0,  # right
    3: 0.0,  # down
    4: -90.0,   # left
}

# Blender units assumed as centimeters; convert to inches
CENTIMETER_TO_INCH = 0.3937007874015748


def get_scene_face_enum_items():
    """Enum items for dropdown (up/right/down/left)."""
    return [
        ("1", "Up", "Face up (0°)"),
        ("2", "Right", "Face right (-90°)"),
        ("3", "Down", "Face down (180°)"),
        ("4", "Left", "Face left (90°)"),
    ]


def face_value_to_rz_rad(face_value: str) -> float:
    """Convert dropdown string value ('1'..'4') to Z rotation in radians."""
    idx = int(face_value)
    deg = FACE_ROTATIONS_DEG[idx]
    return math.radians(deg)


def rotation_to_face_index(rz_rad: float) -> int:
    """
    Read rotation Z (radians) and translate to dropdown key (1~4),
    using closest angle on a circle.
    """
    deg = math.degrees(rz_rad)

    def ang_diff(a, b):
        d = (a - b + 180.0) % 360.0 - 180.0
        return abs(d)

    best_face = 1
    best_diff = 9999.0
    for face_idx, target_deg in FACE_ROTATIONS_DEG.items():
        diff = ang_diff(deg, target_deg)
        if diff < best_diff:
            best_diff = diff
            best_face = face_idx

    return best_face


def is_qr_cone(obj: bpy.types.Object) -> bool:
    """Check if an object is one of our cones (tagged with custom property)."""
    return bool(obj.get("is_qr_cone"))


def get_or_create_qr_collection(scene: bpy.types.Scene) -> bpy.types.Collection:
    """Get or create the collection that stores all QR cones."""
    coll = bpy.data.collections.get(QR_COLLECTION_NAME)
    if coll is None:
        coll = bpy.data.collections.new(QR_COLLECTION_NAME)
        scene.collection.children.link(coll)
    return coll


def delete_all_qr_cones(scene: bpy.types.Scene):
    """Delete all cones created by this tool."""
    objs_to_delete = [obj for obj in scene.objects if is_qr_cone(obj)]
    for obj in objs_to_delete:
        bpy.data.objects.remove(obj, do_unlink=True)


def location_on_top_plane(context, event, plane_z: float = 0.0):
    """
    Compute click location on the top (XY) plane (Z = plane_z),
    using the current view (ideal in TOP view).
    """
    region = context.region
    rv3d = context.region_data
    coord = (event.mouse_region_x, event.mouse_region_y)

    # Build ray from view
    view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
    ray_dir = view_vector.normalized()

    # Plane: z = plane_z, normal (0, 0, 1)
    plane_point = mathutils.Vector((0.0, 0.0, plane_z))
    plane_normal = mathutils.Vector((0.0, 0.0, 1.0))

    denom = ray_dir.dot(plane_normal)
    if abs(denom) < 1e-6:
        # Ray parallel to plane; fallback in front of view
        return ray_origin + ray_dir * 10.0

    t = (plane_point - ray_origin).dot(plane_normal) / denom
    if t < 0:
        # Plane is "behind" the camera; fallback
        return ray_origin + ray_dir * 10.0

    return ray_origin + ray_dir * t


def add_qr_cone_at_location(context, location):
    """
    Add a cone at 'location' with rotation (90°, 0°, rz) where
    rz depends on scene.qr_cone_face.
    Cone is made bigger than default and stored in QR_Cones collection.
    """
    scene = context.scene
    face_value = scene.qr_cone_face  # "1".."4"
    rz = face_value_to_rz_rad(face_value)

    # Replace all previous cones if the option is on
    if scene.qr_cone_replace_all:
        delete_all_qr_cones(scene)

    # Create cone (bigger: adjust radius1 & depth)
    bpy.ops.mesh.primitive_cone_add(
        location=location,
        rotation=(math.radians(90.0), 0.0, rz),
        radius1=0.2,   # base radius (bigger)
        depth=0.5,     # height (bigger)
    )
    cone = context.active_object

    # Tag it as our QR cone and store face index
    cone["is_qr_cone"] = True
    cone["qr_face"] = int(face_value)

    # Ensure the cone is in the QR_Cones collection
    qr_coll = get_or_create_qr_collection(scene)

    # Keep object only in QR collection (cleaner)
    for c in list(cone.users_collection):
        c.objects.unlink(cone)
    qr_coll.objects.link(cone)


# ------------------------------------------------------------------------
# Operators
# ------------------------------------------------------------------------

class OBJECT_OT_qr_cone_place(bpy.types.Operator):
    """Click once in 3D View to place ONE cone (auto switch to TOP view)"""
    bl_idname = "object.qr_cone_place"
    bl_label = "Add Cone (Click once)"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        if context.area.type == 'VIEW_3D':
            # Switch current 3D view to TOP view (orthographic)
            bpy.ops.view3d.view_axis('INVOKE_DEFAULT', type='TOP')

            context.window_manager.modal_handler_add(self)
            self.report({'INFO'}, "Left click once in TOP view to add a cone. ESC to cancel.")
            return {'RUNNING_MODAL'}
        self.report({'WARNING'}, "View3D not found, cannot run operator.")
        return {'CANCELLED'}

    def modal(self, context, event):
        # Cancel
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            return {'CANCELLED'}

        # Place ONE cone on left click, then finish
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            location = location_on_top_plane(context, event, plane_z=0.0)
            add_qr_cone_at_location(context, location)
            return {'FINISHED'}

        return {'PASS_THROUGH'}


class OBJECT_OT_qr_cone_apply_face(bpy.types.Operator):
    """Set selected cone's rotation Z from dropdown"""
    bl_idname = "object.qr_cone_apply_face"
    bl_label = "Set Selected Cone Face"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    def execute(self, context):
        scene = context.scene
        obj = context.active_object

        if not is_qr_cone(obj):
            self.report({'WARNING'}, "Active object is not a QR cone (is_qr_cone property missing).")
            return {'CANCELLED'}

        face_value = scene.qr_cone_face  # "1".."4"
        rz = face_value_to_rz_rad(face_value)

        # Keep current X/Y rotations, only change Z
        rot = obj.rotation_euler
        rot.z = rz
        obj.rotation_euler = rot

        # Update stored face index
        obj["qr_face"] = int(face_value)

        return {'FINISHED'}


class OBJECT_OT_qr_cone_export_json(bpy.types.Operator, ExportHelper):
    """Export all QR cones to JSON"""
    bl_idname = "object.qr_cone_export_json"
    bl_label = "Export QR Cones to JSON"
    bl_options = {'REGISTER'}

    filename_ext = ".json"

    filter_glob: bpy.props.StringProperty(
        default="*.json",
        options={'HIDDEN'},
    )

    def execute(self, context):
        scene = context.scene
        qrcodes = []

        for obj in scene.objects:
            if not is_qr_cone(obj):
                continue

            # World location
            loc_world = obj.matrix_world.translation
            x_inch = loc_world.x * CENTIMETER_TO_INCH
            y_inch = loc_world.y * CENTIMETER_TO_INCH

            # Convert rotation.z to face index (1~4)
            face_idx = rotation_to_face_index(obj.rotation_euler.z)

            qrcodes.append({
                "name": obj.name,
                "x": float(f"{x_inch:.3f}"),
                "y": float(f"{y_inch:.3f}"),
                "face": face_idx,
            })

        data = {
            "qrcodes": qrcodes
        }

        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as ex:
            self.report({'ERROR'}, f"Failed to write JSON: {ex}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported {len(qrcodes)} cones to JSON.")
        return {'FINISHED'}


# ------------------------------------------------------------------------
# UI Panel
# ------------------------------------------------------------------------

class VIEW3D_PT_qr_cone_tools(bpy.types.Panel):
    """Panel in the 3D Viewport N-panel"""
    bl_label = "QR Cones"
    bl_idname = "VIEW3D_PT_qr_cone_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "QR Cones"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        col = layout.column(align=True)
        col.label(text="Face Direction:")
        col.prop(scene, "qr_cone_face", text="Face")

        col = layout.column(align=True)
        col.prop(scene, "qr_cone_replace_all", text="Replace All Previous Cones")

        layout.separator()

        col = layout.column(align=True)
        col.operator("object.qr_cone_place", icon='MESH_CONE')
        col.operator("object.qr_cone_apply_face", icon='ORIENTATION_GIMBAL')

        layout.separator()
        col = layout.column(align=True)
        col.operator("object.qr_cone_export_json", icon='EXPORT')


# ------------------------------------------------------------------------
# Register / Unregister
# ------------------------------------------------------------------------

classes = (
    OBJECT_OT_qr_cone_place,
    OBJECT_OT_qr_cone_apply_face,
    OBJECT_OT_qr_cone_export_json,
    VIEW3D_PT_qr_cone_tools,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.qr_cone_face = EnumProperty(
        name="Face",
        description="QR cone facing direction",
        items=get_scene_face_enum_items(),
        default="1",  # Up
    )

    bpy.types.Scene.qr_cone_replace_all = BoolProperty(
        name="Replace All Previous",
        description="When placing a cone, delete all previous QR cones first",
        default=False,
    )


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.qr_cone_face
    del bpy.types.Scene.qr_cone_replace_all


if __name__ == "__main__":
    register()
