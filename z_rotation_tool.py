"""Utilities for rotating objects around the Z axis."""

import bpy

# ========== Z ROTATION TOOL ==========


def set_origin_and_rotate_z(obj, angle):
    """Set origin to cursor and rotate object around Z axis."""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    obj.rotation_euler.z += angle
    obj.select_set(False)


class OBJECT_OT_add_rotation_z_selected(bpy.types.Operator):
    """Rotate all selected mesh objects around Z axis."""

    bl_idname = "object.add_rotation_z_selected"
    bl_label = "Rotate Selected"

    def execute(self, context):
        angle = context.scene.ar_z_rotation_angle
        count = 0
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                set_origin_and_rotate_z(obj, angle)
                count += 1
        self.report({'INFO'}, f"已套用到 {count} 個選取物件")
        return {'FINISHED'}


class OBJECT_OT_add_rotation_z_all(bpy.types.Operator):
    """Rotate every mesh object in the scene around Z axis."""

    bl_idname = "object.add_rotation_z_all"
    bl_label = "Rotate All"

    def execute(self, context):
        angle = context.scene.ar_z_rotation_angle
        count = 0
        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH':
                set_origin_and_rotate_z(obj, angle)
                count += 1
        self.report({'INFO'}, f"已套用到 {count} 個全部物件")
        return {'FINISHED'}


class OBJECT_PT_change_rotation_z(bpy.types.Panel):
    """Panel for applying Z axis rotations."""

    bl_label = "Change Rotation Z"
    bl_idname = "OBJECT_PT_change_rotation_z"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AR Tool Box"

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, "ar_z_rotation_angle")
        layout.operator("object.add_rotation_z_selected", icon='STICKY_UVS_LOC')
        layout.operator("object.add_rotation_z_all", icon='STICKY_UVS_DISABLE')


classes = (
    OBJECT_OT_add_rotation_z_selected,
    OBJECT_OT_add_rotation_z_all,
    OBJECT_PT_change_rotation_z,
)


def register():
    """Register rotation operators and scene properties."""
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.ar_z_rotation_angle = bpy.props.FloatProperty(
        name="Z",
        description="Z Axis Rotation in Degrees",
        default=0.0,
        subtype='ANGLE',
        unit='ROTATION',
    )


def unregister():
    """Unregister rotation operators and remove properties."""
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.ar_z_rotation_angle
