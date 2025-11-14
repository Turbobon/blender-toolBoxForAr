import bpy
import mathutils
from bpy_extras import view3d_utils

# ---------- Properties ----------
class PointPickerProps(bpy.types.PropertyGroup):
    x: bpy.props.FloatProperty(name="X")
    y: bpy.props.FloatProperty(name="Y")
    z: bpy.props.FloatProperty(name="Z", description="Hit Z (for reference)")

# ---------- Modal Picker ----------
class VIEW3D_OT_pick_xy_topview(bpy.types.Operator):
    """Click in Top view to capture XY once"""
    bl_idname = "view3d.pick_xy_topview"
    bl_label = "Pick XY (Top View)"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        if context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Run from a 3D Viewport sidebar button")
            return {'CANCELLED'}

        # Switch to Top Ortho view
        bpy.ops.view3d.view_axis(type='TOP')
        bpy.ops.view3d.view_persportho()

        context.window_manager.modal_handler_add(self)
        self._set_status_text(context, enable=True)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self._set_status_text(context, enable=False)
            return {'CANCELLED'}

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self.pick_at_mouse(context, event)
            self._set_status_text(context, enable=False)
            return {'FINISHED'}  # ✅ stop after first pick

        return {'RUNNING_MODAL'}

    def pick_at_mouse(self, context, event):
        region = context.region
        rv3d = context.space_data.region_3d
        coord = (event.mouse_region_x, event.mouse_region_y)

        origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
        direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)

        depsgraph = context.evaluated_depsgraph_get()
        hit, loc, normal, index, obj, matrix = context.scene.ray_cast(depsgraph, origin, direction)

        if hit:
            world_loc = loc
        else:
            world_loc = self._intersect_ray_with_z_plane(origin, direction, z=0.0)
            if world_loc is None:
                self.report({'WARNING'}, "Ray parallel to XY plane; try another spot")
                return

        props = context.scene.point_picker_props
        props.x, props.y, props.z = world_loc.x, world_loc.y, world_loc.z
        self.report({'INFO'}, f"Picked: X={props.x:.4f}, Y={props.y:.4f}, Z={props.z:.4f}")

    def _intersect_ray_with_z_plane(self, origin: mathutils.Vector, direction: mathutils.Vector, z=0.0):
        if abs(direction.z) < 1e-8:
            return None
        t = (z - origin.z) / direction.z
        if t < 0:
            return None
        return origin + direction * t

    def _set_status_text(self, context, enable=True):
        header = context.area.header_text_set
        if enable:
            header("Pick XY once (LMB to pick, RMB/Esc to cancel)")
        else:
            header(None)

# ---------- UI Panel ----------
class VIEW3D_PT_PointPickerTop(bpy.types.Panel):
    bl_label = "Top-View XY Picker"
    bl_idname = "VIEW3D_PT_point_picker_top"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Demo'

    def draw(self, context):
        layout = self.layout
        props = context.scene.point_picker_props
        layout.operator("view3d.pick_xy_topview", icon='MOUSE_LMB')
        col = layout.column(align=True)
        col.prop(props, "x")
        col.prop(props, "y")
        col.prop(props, "z")

# ---------- Register ----------
classes = (
    PointPickerProps,
    VIEW3D_OT_pick_xy_topview,
    VIEW3D_PT_PointPickerTop,
)

def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.point_picker_props = bpy.props.PointerProperty(type=PointPickerProps)

def unregister():
    del bpy.types.Scene.point_picker_props
    for c in reversed(classes):
        bpy.utils.unregister_class(c)

if __name__ == "__main__":
    register()
