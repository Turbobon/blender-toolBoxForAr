import bpy
import mathutils
from mathutils import Vector, Matrix
from math import pi
from bpy_extras import view3d_utils
import json

# ---------------- Properties ----------------
class PointPickerProps(bpy.types.PropertyGroup):
    x: bpy.props.FloatProperty(name="X", options={'HIDDEN'})
    y: bpy.props.FloatProperty(name="Y", options={'HIDDEN'})
    z: bpy.props.FloatProperty(name="Z", options={'HIDDEN'})
    cone_radius: bpy.props.FloatProperty(name="Cone Radius", default=0.2, min=0.001)
    cone_height: bpy.props.FloatProperty(name="Cone Height", default=0.5, min=0.001)
    replace_previous: bpy.props.BoolProperty(
        name="Replace Previous",
        description="Delete previously placed marker cones",
        default=False
    )

# ---------------- Helpers ----------------
def get_or_create_blue_mat():
    name = "PickerBlue"
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.10, 0.40, 1.00, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.35
    return mat

def get_or_create_marker_collection():
    col_name = "PickMarkers"
    col = bpy.data.collections.get(col_name)
    if col is None:
        col = bpy.data.collections.new(col_name)
        bpy.context.scene.collection.children.link(col)
    return col

def align_z_to_vector(vec: Vector) -> Matrix:
    """Return rotation matrix that rotates +Z to 'vec' (normalized)."""
    z = Vector((0, 0, 1))
    v = vec.normalized()
    if (v - z).length < 1e-8:
        return Matrix.Identity(3).to_4x4()
    if (v + z).length < 1e-8:
        # 180° flip around X (any axis perpendicular to Z works)
        return Matrix.Rotation(pi, 4, 'X')
    quat = z.rotation_difference(v)
    return quat.to_matrix().to_4x4()

def place_cone(world_loc: Vector, normal: Vector, radius: float, height: float, replace_previous: bool):
    # Optionally clear older cones
    if replace_previous:
        col = get_or_create_marker_collection()
        for obj in list(col.objects):
            bpy.data.objects.remove(obj, do_unlink=True)

    # Add cone at origin, then set transform
    bpy.ops.mesh.primitive_cone_add(
        vertices=32,
        radius1=radius,
        radius2=0.0,
        depth=height,
        enter_editmode=False,
        location=(0, 0, 0),
        rotation=(0, 0, 0)
    )
    cone = bpy.context.active_object
    cone.name = "PickCone"

    # Material
    mat = get_or_create_blue_mat()
    if cone.data.materials:
        cone.data.materials[0] = mat
    else:
        cone.data.materials.append(mat)

    # Align cone's +Z to surface normal; base on surface, tip up
    rot_m = align_z_to_vector(normal if normal.length > 0 else Vector((0, 0, 1)))
    translate = Matrix.Translation(world_loc)
    # primitive_cone_add centers at origin, extends +/- height/2 along Z.
    # To put base at surface, raise by height/2 in local Z.
    lift_local = Matrix.Translation(Vector((0, 0, height / 2.0)))
    cone.matrix_world = translate @ rot_m @ lift_local

    # Put into marker collection
    col = get_or_create_marker_collection()
    if cone.name not in col.objects:
        col.objects.link(cone)
    for parent in list(cone.users_collection):
        if parent is not col:
            parent.objects.unlink(cone)

    return cone

# ---------------- Pick & Place Cone Operator ----------------
class VIEW3D_OT_pick_xy_make_cone(bpy.types.Operator):
    """Click once in Top view to place a blue cone at the picked spot"""
    bl_idname = "view3d.pick_xy_make_cone"
    bl_label = "Pick & Place Cone (Top View)"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        if context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Run from a 3D Viewport sidebar button")
            return {'CANCELLED'}
        # Switch to Top Ortho
        bpy.ops.view3d.view_axis(type='TOP')
        bpy.ops.view3d.view_persportho()
        context.window_manager.modal_handler_add(self)
        self._set_status_text(context, True)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self._set_status_text(context, False)
            return {'CANCELLED'}

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self.pick_and_build(context, event)
            self._set_status_text(context, False)
            return {'FINISHED'}  # stop after first pick

        return {'RUNNING_MODAL'}

    def pick_and_build(self, context, event):
        region = context.region
        rv3d = context.space_data.region_3d
        coord = (event.mouse_region_x, event.mouse_region_y)

        origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
        direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)

        depsgraph = context.evaluated_depsgraph_get()
        hit, loc, normal, index, obj, matrix = context.scene.ray_cast(depsgraph, origin, direction)

        props = context.scene.point_picker_props

        if hit:
            world_loc = loc
            nrm = normal if normal.length > 1e-8 else Vector((0, 0, 1))
        else:
            # Intersect with Z=0 plane
            if abs(direction.z) < 1e-8:
                self.report({'WARNING'}, "Ray parallel to XY plane; try another spot")
                return
            t = (0.0 - origin.z) / direction.z
            if t < 0:
                self.report({'WARNING'}, "Click in front of the camera")
                return
            world_loc = origin + direction * t
            nrm = Vector((0, 0, 1))

        # Save XYZ to props (still in Blender units)
        props.x, props.y, props.z = world_loc.x, world_loc.y, world_loc.z

        # Create cone
        place_cone(
            world_loc,
            nrm,
            radius=props.cone_radius,
            height=props.cone_height,
            replace_previous=props.replace_previous
        )

        self.report({'INFO'}, f"Cone placed at X={props.x:.3f}, Y={props.y:.3f}, Z={props.z:.3f}")

    def _set_status_text(self, context, enable=True):
        header = context.area.header_text_set
        header("LMB: place cone • RMB/Esc: cancel" if enable else None)

# ---------------- Export JSON Operator ----------------
class VIEW3D_OT_export_pickcones_json(bpy.types.Operator):
    """Export all PickCones' (x,y) in inches as JSON"""
    bl_idname = "view3d.export_pickcones_json"
    bl_label = "Export PickCones JSON"

    def execute(self, context):
        col = bpy.data.collections.get("PickMarkers")
        if not col:
            self.report({'WARNING'}, "No 'PickMarkers' collection found")
            return {'CANCELLED'}

        # Conversion (Blender units -> inches)
        METER_TO_INCH = 39.37007874

        data = []
        for obj in col.objects:
            if obj.type == 'MESH' and obj.name.startswith("PickCone"):
                loc = obj.matrix_world.translation
                data.append({
                    "name": obj.name,
                    "x_in": loc.x * METER_TO_INCH,
                    "y_in": loc.y * METER_TO_INCH
                })

        if not data:
            self.report({'WARNING'}, "No PickCone objects found")
            return {'CANCELLED'}

        json_str = json.dumps(data, indent=2)

        # ----------- WRITE TO FILE -----------
        file_path = r"C:\Users\User\Desktop\_forge\KSNZ - 0911\pickcones.json"

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(json_str)

            self.report({'INFO'}, f"JSON exported to {file_path}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to write file: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}

# ---------------- UI Panel ----------------
class VIEW3D_PT_PointPickerTop(bpy.types.Panel):
    bl_label = "Top-View XY Picker"
    bl_idname = "VIEW3D_PT_point_picker_top"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Demo'

    def draw(self, context):
        layout = self.layout
        p = context.scene.point_picker_props

        layout.operator("view3d.pick_xy_make_cone", icon='MOUSE_LMB')
        layout.prop(p, "replace_previous")
        layout.separator()
        col = layout.column(align=True)
        col.prop(p, "cone_radius")
        col.prop(p, "cone_height")
        layout.separator()
        layout.operator("view3d.export_pickcones_json", icon='EXPORT')
        layout.separator()
        row = layout.row(align=True)
        row.label(text=f"Last Pick XY (BU): ({p.x:.3f}, {p.y:.3f})")

# ---------------- Register ----------------
classes = (
    PointPickerProps,
    VIEW3D_OT_pick_xy_make_cone,
    VIEW3D_OT_export_pickcones_json,
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
