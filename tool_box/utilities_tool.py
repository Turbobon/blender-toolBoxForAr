"""Miscellaneous utility operators used across the AR workflow."""

import os
import zipfile
import bpy
from mathutils import Vector

# ========== AR UTILITIES TOOL ==========


class OBJECT_OT_run_selected_utilities(bpy.types.Operator):
    """Execute selected utility operations on the current scene."""

    bl_idname = "object.run_selected_utilities"
    bl_label = "Utilities Changes"
    bl_description = "依據勾選的功能執行操作"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene

        if scene.rename_mesh_data:
            for obj in scene.objects:
                if obj.type == 'MESH':
                    original_data = obj.data
                    if original_data.users > 1:
                        obj.data = original_data.copy()
                    obj.data.name = obj.name
            self.report({'INFO'}, "已完成 mesh name 置換")

        if scene.assign_default_material:
            new_material_name = "none_mat"
            if new_material_name not in bpy.data.materials:
                new_material = bpy.data.materials.new(name=new_material_name)
            else:
                new_material = bpy.data.materials[new_material_name]

            for obj in scene.objects:
                if obj.type == 'MESH':
                    if not obj.data.materials:
                        obj.data.materials.append(new_material)
                        print(f"已為物件 {obj.name} 添加材質 {new_material_name}")
                    else:
                        print(f"物件 {obj.name} 已經有材質")

        if scene.set_material_to_blend:
            for mat in bpy.data.materials:
                mat.use_nodes = False
                mat.blend_method = 'BLEND'
            self.report({'INFO'}, "已將所有材質設為 BLEND 模式")

        return {'FINISHED'}


class OBJECT_OT_move_objects_to_center(bpy.types.Operator):
    """Move all mesh objects so that the model is centered around origin."""

    bl_idname = "object.move_objects_to_center"
    bl_label = "Move Model"

    def execute(self, context):
        min_x, min_y, min_z = float('inf'), float('inf'), float('inf')
        max_x, max_y, max_z = float('-inf'), float('-inf'), float('-inf')

        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH':
                for vertex in obj.bound_box:
                    world_vertex = obj.matrix_world @ Vector(vertex)
                    min_x = min(min_x, world_vertex.x)
                    max_x = max(max_x, world_vertex.x)
                    min_y = min(min_y, world_vertex.y)
                    max_y = max(max_y, world_vertex.y)
                    min_z = min(min_z, world_vertex.z)
                    max_z = max(max_z, world_vertex.z)

        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        center_z = (min_z + max_z) / 2

        def move_obj(obj):
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            obj.location.x -= center_x
            obj.location.y -= center_y
            obj.location.z -= center_z
            bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
            obj.select_set(False)

        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH':
                move_obj(obj)

        self.report({'INFO'}, "所有物件已移動至中心點")
        return {'FINISHED'}


class OBJECT_OT_cut_all_objects(bpy.types.Operator):
    """Bisect every mesh object along a chosen axis."""

    bl_idname = "object.cut_all_objects"
    bl_label = "Cut All Mesh Objects"

    def execute(self, context):
        cut_objects(context, only_selected=False)
        self.report({'INFO'}, "所有物件裁切完成")
        return {'FINISHED'}


class OBJECT_OT_cut_selected_objects(bpy.types.Operator):
    """Bisect only the selected mesh objects."""

    bl_idname = "object.cut_selected_objects"
    bl_label = "Cut Selected Objects"

    def execute(self, context):
        cut_objects(context, only_selected=True)
        self.report({'INFO'}, "選取物件裁切完成")
        return {'FINISHED'}


def cut_objects(context, only_selected):
    """Helper to bisect objects along an axis.

    Parameters
    ----------
    context : bpy.types.Context
        Blender context containing scene information.
    only_selected : bool
        If True, only selected objects are processed; otherwise all objects.
    """
    axis = context.scene.cut_axis.lower()
    direction = context.scene.cut_direction
    distance = context.scene.cut_distance

    index_map = {'x': 0, 'y': 1, 'z': 2}
    co = Vector((0, 0, 0))
    co[index_map[axis]] = distance

    axis_map = {'x': Vector((1, 0, 0)), 'y': Vector((0, 1, 0)), 'z': Vector((0, 0, 1))}
    no = axis_map[axis]

    target_objects = context.selected_objects if only_selected else context.scene.objects

    for obj in list(target_objects):
        if obj.type != 'MESH':
            continue

        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')

        bpy.ops.mesh.bisect(
            plane_co=co,
            plane_no=no,
            use_fill=True,
            clear_inner=(direction == '-'),
            clear_outer=(direction == '+'),
        )

        bpy.ops.object.mode_set(mode='OBJECT')
        obj.select_set(False)

    return


class OBJECT_OT_export_model(bpy.types.Operator):
    """Export scene to glTF/GLB/USDZ formats and bundle as ZIP."""

    bl_idname = "object.export_model"
    bl_label = "Export glTF/GLB/USDZ"
    bl_description = "匯出 glTF、GLB、USDZ"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        blend_path = bpy.data.filepath
        if not blend_path:
            self.report({'ERROR'}, "請先儲存 .blend 檔案才能匯出")
            return {'CANCELLED'}

        originalname = bpy.path.display_name_from_filepath(blend_path)

        if context.scene.export_filename.strip() != '':
            filename = context.scene.export_filename.strip()
        else:
            filename = originalname
        base_dir = os.path.dirname(blend_path)

        main_dir = os.path.join(base_dir, filename)
        name_dir = os.path.join(main_dir, originalname)
        os.makedirs(name_dir, exist_ok=True)
        gltf_dir = os.path.join(main_dir, f"{filename}")
        os.makedirs(gltf_dir, exist_ok=True)

        gltf_path = os.path.join(gltf_dir, f"{filename}.gltf")
        bpy.ops.export_scene.gltf(
            filepath=gltf_path,
            export_format='GLTF_SEPARATE',
            use_selection=False,
            use_visible=True,
            export_apply=True,
        )

        glb_path = os.path.join(gltf_dir, f"{filename}.glb")
        bpy.ops.export_scene.gltf(
            filepath=glb_path,
            export_format='GLB',
            use_selection=False,
            use_visible=True,
            export_apply=True,
        )

        usdz_path = os.path.join(main_dir, f"{filename}.usdz")
        bpy.ops.wm.usd_export(
            filepath=usdz_path,
            visible_objects_only=True,
            selected_objects_only=False,
            export_animation=False,
            export_materials=True,
            export_textures=True,
        )

        zip_path = os.path.join(main_dir, f"{filename}.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(gltf_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, gltf_dir)
                    zipf.write(file_path, arcname)

        self.report({'INFO'}, f"✅ 匯出完成，Zip 位置：{zip_path}")
        return {'FINISHED'}


class OBJECT_PT_utility_panel(bpy.types.Panel):
    """Panel grouping all miscellaneous utilities for AR models."""

    bl_label = "Utility Changes"
    bl_idname = "OBJECT_PT_utility_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AR Tool Box"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        box1 = layout.box()
        row = box1.row()
        row.prop(scene, "accordion_change_props", icon="TRIA_DOWN" if scene.accordion_change_props else "TRIA_RIGHT", icon_only=True, emboss=False)
        row.label(text="Select and Change Props")
        if scene.accordion_change_props:
            box1.prop(scene, "rename_mesh_data")
            box1.prop(scene, "assign_default_material")
            box1.prop(scene, "set_material_to_blend")
            box1.operator("object.run_selected_utilities")

        box2 = layout.box()
        row = box2.row()
        row.prop(scene, "accordion_move_to_origin", icon="TRIA_DOWN" if scene.accordion_move_to_origin else "TRIA_RIGHT", icon_only=True, emboss=False)
        row.label(text="Move to Origin")
        if scene.accordion_move_to_origin:
            box2.operator("object.move_objects_to_center", icon='PIVOT_ACTIVE')

        box3 = layout.box()
        row = box3.row()
        row.prop(scene, "accordion_axis_cut", icon="TRIA_DOWN" if scene.accordion_axis_cut else "TRIA_RIGHT", icon_only=True, emboss=False)
        row.label(text="Axis Cut")
        if scene.accordion_axis_cut:
            box3.prop(scene, "cut_axis", text="Axis")
            box3.prop(scene, "cut_direction", text="Direction")
            box3.prop(scene, "cut_distance", text="Cut From")
            box3.operator("object.cut_all_objects", icon='MOD_BOOLEAN')
            box3.operator("object.cut_selected_objects", icon='RESTRICT_SELECT_OFF')

        layout.separator()

        box4 = layout.box()
        row = box4.row()
        row.prop(scene, "export_model_for_app", icon="TRIA_DOWN" if scene.export_model_for_app else "TRIA_RIGHT", icon_only=True, emboss=False)
        row.label(text="Export for app")
        if scene.export_model_for_app:
            box4.prop(scene, "export_filename", text="Files Name")
            box4.operator("object.export_model", icon='EXPORT')


classes = (
    OBJECT_OT_run_selected_utilities,
    OBJECT_OT_move_objects_to_center,
    OBJECT_OT_cut_all_objects,
    OBJECT_OT_cut_selected_objects,
    OBJECT_OT_export_model,
    OBJECT_PT_utility_panel,
)


def register():
    """Register utility operators, panel, and scene properties."""
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.rename_mesh_data = bpy.props.BoolProperty(
        name="Named .usd Element by Name",
        default=True,
    )
    bpy.types.Scene.assign_default_material = bpy.props.BoolProperty(
        name="Prevent Material Loss",
        default=True,
    )
    bpy.types.Scene.set_material_to_blend = bpy.props.BoolProperty(
        name="Prevent Color Loss",
        default=True,
    )
    bpy.types.Scene.cut_axis = bpy.props.EnumProperty(
        name="Axis",
        items=[('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", "")],
        default='Z',
    )
    bpy.types.Scene.cut_direction = bpy.props.EnumProperty(
        name="Direction",
        items=[('+', "+ (Cut positive)", "Cut positive side"), ('-', "- (Cut negative)", "Cut negative side")],
        default='+',
    )
    bpy.types.Scene.cut_distance = bpy.props.FloatProperty(
        name="Cut From",
        default=0.0,
        unit='LENGTH',
        subtype='DISTANCE',
    )
    bpy.types.Scene.export_filename = bpy.props.StringProperty(
        name="FilesName",
        description="File name for files export",
        default="",
    )
    bpy.types.Scene.accordion_change_props = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.accordion_move_to_origin = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.accordion_axis_cut = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.export_model_for_app = bpy.props.BoolProperty(default=True)


def unregister():
    """Unregister classes and clean up scene properties."""
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.rename_mesh_data
    del bpy.types.Scene.assign_default_material
    del bpy.types.Scene.set_material_to_blend
    del bpy.types.Scene.cut_axis
    del bpy.types.Scene.cut_direction
    del bpy.types.Scene.cut_distance
    del bpy.types.Scene.export_filename
    del bpy.types.Scene.accordion_change_props
    del bpy.types.Scene.accordion_move_to_origin
    del bpy.types.Scene.accordion_axis_cut
    del bpy.types.Scene.export_model_for_app
