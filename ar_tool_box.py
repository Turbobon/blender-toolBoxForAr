bl_info = {
    "name": "AR Tool Box",
    "author": "Bimfm_Annie Sung",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > AR Tool Box",
    "description": "Includes Z Rotation Tool and IFC ElementId Renamer",
    "category": "Object",
}

import bpy
import math
import os
import zipfile
from mathutils import Vector

# ========== Z ROTATION TOOL ==========
def set_origin_and_rotate_z(obj, angle):
    bpy.context.view_layer.objects.active = obj # 將當前物件設為 active，並選取它
    obj.select_set(True)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR') # 將 origin 設為 3D 游標
    obj.rotation_euler.z += angle
    obj.select_set(False) # 清除選取（避免干擾）

## Buttom [將選取物件的RotationZ都加上一個數值]
class OBJECT_OT_add_rotation_z_selected(bpy.types.Operator):
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

## Buttom [將所有物件的RotationZ都加上一個數值]
class OBJECT_OT_add_rotation_z_all(bpy.types.Operator):
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

# ========== IFC RENAME TOOL ==========
## 更新匯出路徑輸入框
def update_ifc_output(self, context):
    input_path = self.ar_ifc_input_path
    if input_path:
        import os
        name, ext = os.path.splitext(input_path)
        context.scene.ar_ifc_output_path = name + "_id" + ext

## 用ElementId改變物件名稱(主邏輯)
def name_ifc_elements_by_tag(ifcopenshell, file_path, output_path, prefix):
    if prefix != '':
        prefix = f'_{prefix}'
    ifc = ifcopenshell.open(file_path)
    listType = ['IfcColumn', 'IfcCurtainWall', 'IfcWall', 'IfcWallStandardCase',
                    'IfcFlowFitting', 'IfcFlowSegment', 'IfcFlowTerminal',
                    'IfcDistributionControlElement', 'IfcFlowController',
                    'IfcFurnishingElement', 'IfcPlate', 'IfcSlab', 'IfcDoor',
                    'IfcBuildingElementProxy', 'IfcStair', 'IfcBeam', 'IfcStairFlight',
                    'IfcMember', 'IfcCovering']
    for type_name in listType:
        for ele in ifc.by_type(type_name):
            ele.Name = f'{prefix}_{ele.Tag}'
    ifc.write(output_path)

## Buttom [匯出以ElementId命名的IFC]
class OBJECT_OT_rename_ifc_elements(bpy.types.Operator):
    bl_idname = "object.rename_ifc_elements"
    bl_label = "Rename"
    def execute(self, context):
        try:
            import ifcopenshell
        except ImportError:
            self.report({'ERROR'}, "需要安裝 ifcopenshell 套件")
            return {'CANCELLED'}

        path = context.scene.ar_ifc_input_path
        if not os.path.isfile(path):
            self.report({'ERROR'}, "IFC 檔案路徑無效")
            return {'CANCELLED'}
        outpath = context.scene.ar_ifc_output_path
        output_dir = os.path.dirname(outpath)
        if not os.path.isdir(output_dir):
            self.report({'ERROR'}, "輸出資料夾路徑無效")
            return {'CANCELLED'}

        file_path = path
        outtput_file_path_without_ext = os.path.splitext(outpath)[0]
        file_ext = os.path.splitext(file_path)[1]
        export_file_name = outtput_file_path_without_ext + file_ext
        context.scene.ar_ifc_output_path = export_file_name

        prefix = context.scene.ar_ifc_prefix.strip()
        if not prefix:
            prefix = ''
        name_ifc_elements_by_tag(ifcopenshell, file_path, export_file_name, prefix)

        self.report({'INFO'}, f"已產出新 IFC：{export_file_name}")
        return {'FINISHED'}
    
## Buttom [將資料夾中的IFC 以ElementId命名 並生成另一個資料夾]
class OBJECT_OT_batch_rename_ifc_folder(bpy.types.Operator):
    bl_idname = "object.batch_rename_ifc_folder"
    bl_label = "Batch Rename Folder"

    def execute(self, context):
        try:
            import ifcopenshell
        except ImportError:
            self.report({'ERROR'}, "需要安裝 ifcopenshell 套件")
            return {'CANCELLED'}

        folder_path = context.scene.ar_ifc_folder_path
        if not os.path.isdir(folder_path):
            self.report({'ERROR'}, "資料夾路徑無效")
            return {'CANCELLED'}
        
        use_prefix = context.scene.use_filename_as_prefix
        count = 0
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(".ifc"):
                    input_path = os.path.join(root, file)

                    # 輸出路徑設為同一資料夾中，加上 _id
                    output_path = os.path.join(root, os.path.splitext(file)[0] + "_id.ifc")

                    try:
                        prefix = os.path.splitext(file)[0] if use_prefix else ""
                        name_ifc_elements_by_tag(ifcopenshell, input_path, output_path, prefix)
                        count += 1
                    except Exception as e:
                        self.report({'WARNING'}, f"{file} 轉換失敗：{e}")

        self.report({'INFO'}, f"已處理 {count} 個 IFC 檔案，輸出至原資料夾中")
        return {'FINISHED'}

# ========== AR UTILITIES TOOL ==========
## Buttom [選取需要的功能後執行]
class OBJECT_OT_run_selected_utilities(bpy.types.Operator):
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
    
## Buttom [將物件移動至原點]    
class OBJECT_OT_move_objects_to_center(bpy.types.Operator):
    bl_idname = "object.move_objects_to_center"
    bl_label = "Move Model"

    def execute(self, context):
        from mathutils import Vector

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

## Buttom [用軸線裁切所有物件]
class OBJECT_OT_cut_all_objects(bpy.types.Operator):
    bl_idname = "object.cut_all_objects"
    bl_label = "Cut All Mesh Objects"

    def execute(self, context):
        cut_objects(context, only_selected=False)
        self.report({'INFO'}, "所有物件裁切完成")
        return {'FINISHED'}
    
## Buttom [用軸線裁切選取物件]
class OBJECT_OT_cut_selected_objects(bpy.types.Operator):
    bl_idname = "object.cut_selected_objects"
    bl_label = "Cut Selected Objects"

    def execute(self, context):
        cut_objects(context, only_selected=True)
        self.report({'INFO'}, "選取物件裁切完成")
        return {'FINISHED'}

## 以軸線裁切物件(主邏輯)
def cut_objects(context, only_selected):
    axis = context.scene.cut_axis.lower()  # 'x', 'y', or 'z'
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
            clear_outer=(direction == '+')
        )

        bpy.ops.object.mode_set(mode='OBJECT')
        obj.select_set(False)

    return


## Buttom [匯出.glb、.gltf、.usdz]
class OBJECT_OT_export_model(bpy.types.Operator):
    bl_idname = "object.export_model"
    bl_label = "Export glTF/GLB/USDZ"
    bl_description = "匯出 glTF、GLB、USDZ"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # 取得 .blend 檔案路徑與名稱
        blend_path = bpy.data.filepath
        if not blend_path:
            self.report({'ERROR'}, "請先儲存 .blend 檔案才能匯出")
            return {'CANCELLED'}

        filename = bpy.path.display_name_from_filepath(blend_path)
        base_dir = os.path.dirname(blend_path)

        # 建立目錄
        main_dir = os.path.join(base_dir, filename)
        gltf_dir = os.path.join(main_dir, f"{filename}_gltf")
        os.makedirs(gltf_dir, exist_ok=True)

        # 匯出 GLTF
        gltf_path = os.path.join(gltf_dir, f"{filename}.gltf")
        bpy.ops.export_scene.gltf(
            filepath=gltf_path,
            export_format='GLTF_SEPARATE',
            use_selection=False,
            use_visible=True,
            export_apply=True
        )

        # 匯出 GLB
        glb_path = os.path.join(main_dir, f"{filename}.glb")
        bpy.ops.export_scene.gltf(
            filepath=glb_path,
            export_format='GLB',
            use_selection=False,
            use_visible=True,
            export_apply=True
        )

        # 匯出 USDZ
        usdz_path = os.path.join(main_dir, f"{filename}.usdz")
        bpy.ops.wm.usd_export(
            filepath=usdz_path,
            visible_objects_only=True,
            selected_objects_only=False,
            export_animation=False,
            export_materials=True,
            export_textures=True,
        )

        # 建立 ZIP
        zip_path = os.path.join(main_dir, f"{filename}_gltf.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(gltf_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, gltf_dir)
                    zipf.write(file_path, arcname)

        self.report({'INFO'}, f"✅ 匯出完成，Zip 位置：{zip_path}")
        return {'FINISHED'}
    
# ========== RENAME IFC UI PANEL ==========
class OBJECT_PT_rename_ifc(bpy.types.Panel):
    bl_label = "Rename IFC"
    bl_idname = "OBJECT_PT_rename_ifc"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AR Tool Box"

    def draw(self, context):
        layout = self.layout
        layout.label(text="IFC Name by ElementId")
        layout.prop(context.scene, "ar_ifc_input_path")
        layout.prop(context.scene, "ar_ifc_output_path")
        layout.prop(context.scene, "ar_ifc_prefix")
        layout.operator("object.rename_ifc_elements", icon='FILE_REFRESH')
        layout.separator()
        layout.label(text="Named IFCs in Folder")
        layout.prop(context.scene, "ar_ifc_folder_path")
        layout.prop(context.scene, "use_filename_as_prefix")
        layout.operator("object.batch_rename_ifc_folder", icon='FILE_REFRESH')

# ========== Z ROTATION UI PANEL ==========
class OBJECT_PT_change_rotation_z(bpy.types.Panel):
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

# ========== Utility Changes UI PANEL ==========
class OBJECT_PT_utility_panel(bpy.types.Panel):
    bl_label = "Utility Changes"
    bl_idname = "OBJECT_PT_utility_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AR Tool Box"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Select and Change Props
        box1 = layout.box()
        row = box1.row()
        row.prop(scene, "accordion_change_props", icon="TRIA_DOWN" if scene.accordion_change_props else "TRIA_RIGHT",
                 icon_only=True, emboss=False)
        row.label(text="Select and Change Props")

        if scene.accordion_change_props:
            box1.prop(scene, "rename_mesh_data")
            box1.prop(scene, "assign_default_material")
            box1.prop(scene, "set_material_to_blend")
            box1.operator("object.run_selected_utilities")
        
        # Move to Origin
        box2 = layout.box()
        row = box2.row()
        row.prop(scene, "accordion_move_to_origin", icon="TRIA_DOWN" if scene.accordion_move_to_origin else "TRIA_RIGHT",
                 icon_only=True, emboss=False)
        row.label(text="Move to Origin")

        if scene.accordion_move_to_origin:
            box2.operator("object.move_objects_to_center", icon='PIVOT_ACTIVE')

        # Axis Cut
        box3 = layout.box()
        row = box3.row()
        row.prop(scene, "accordion_axis_cut", icon="TRIA_DOWN" if scene.accordion_axis_cut else "TRIA_RIGHT",
                 icon_only=True, emboss=False)
        row.label(text="Axis Cut")

        if scene.accordion_axis_cut:
            box3.prop(scene, "cut_axis", text="Axis")
            box3.prop(scene, "cut_direction", text="Direction")
            box3.prop(scene, "cut_distance", text="Cut From")
            box3.operator("object.cut_all_objects", icon='MOD_BOOLEAN')
            box3.operator("object.cut_selected_objects", icon='RESTRICT_SELECT_OFF')

        # Export Model
        layout.separator()
        layout.operator("object.export_model", icon='EXPORT')
        
# ========== REGISTER ==========
classes = (
    OBJECT_OT_add_rotation_z_selected,
    OBJECT_OT_add_rotation_z_all,
    OBJECT_OT_rename_ifc_elements,
    OBJECT_OT_batch_rename_ifc_folder,
    OBJECT_OT_run_selected_utilities,
    OBJECT_OT_move_objects_to_center,
    OBJECT_OT_cut_all_objects,
    OBJECT_OT_cut_selected_objects,
    OBJECT_OT_export_model,
    OBJECT_PT_rename_ifc,
    OBJECT_PT_change_rotation_z,
    OBJECT_PT_utility_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.ar_z_rotation_angle = bpy.props.FloatProperty(
        name="Z",
        description="Z Axis Rotation in Degrees",
        default=0.0,
        subtype='ANGLE',
        unit='ROTATION'
    )
    bpy.types.Scene.ar_ifc_input_path = bpy.props.StringProperty(
        name="Input",
        subtype='FILE_PATH',
        update=update_ifc_output
    )
    bpy.types.Scene.ar_ifc_output_path = bpy.props.StringProperty(
        name="Output",
        subtype='FILE_PATH',
    )
    bpy.types.Scene.ar_ifc_prefix = bpy.props.StringProperty(
    name="Prefix",
    description="Prefix for renaming elements",
    default=""
    )
    bpy.types.Scene.use_filename_as_prefix = bpy.props.BoolProperty(
    name="Use FileName as Prefix",
    description="Use IFC FileName as Elements Prefix",
    default=True
    )
    bpy.types.Scene.ar_ifc_folder_path = bpy.props.StringProperty(
        name="Folder",
        subtype='FILE_PATH',
    )
    bpy.types.Scene.rename_mesh_data = bpy.props.BoolProperty(
        name="Named .usd Element by Name",# "將 mesh name 置換為 name"
        default=True
    )
    bpy.types.Scene.assign_default_material = bpy.props.BoolProperty(
        name="Prevent Material Loss",# "賦予所有物件材質"
        default=True
    )
    bpy.types.Scene.set_material_to_blend = bpy.props.BoolProperty(
        name="Prevent Color Loss",# "將材質設為 BLEND 模式，關閉 node"
        default=True
    )
    bpy.types.Scene.cut_axis = bpy.props.EnumProperty(
        name="Axis",
        items=[('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", "")],
        default='Z'
    )
    bpy.types.Scene.cut_direction = bpy.props.EnumProperty(
        name="Direction",
        items=[('+', "+ (Cut positive)", "Cut positive side"), ('-', "- (Cut negative)", "Cut negative side")],
        default='+'
    )
    bpy.types.Scene.cut_distance = bpy.props.FloatProperty(
        name="Cut From",
        default=0.0,
        unit='LENGTH',
        subtype='DISTANCE'
    )
    # Toggle fold state
    bpy.types.Scene.accordion_change_props = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.accordion_move_to_origin = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.accordion_axis_cut = bpy.props.BoolProperty(default=True)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.ar_z_rotation_angle
    del bpy.types.Scene.ar_ifc_input_path
    del bpy.types.Scene.ar_ifc_output_path
    del bpy.types.Scene.ar_ifc_prefix
    del bpy.types.Scene.ar_ifc_folder_path
    del bpy.types.Scene.use_filename_as_prefix
    del bpy.types.Scene.rename_mesh_data
    del bpy.types.Scene.assign_default_material
    del bpy.types.Scene.set_material_to_blend
    del bpy.types.Scene.cut_axis
    del bpy.types.Scene.cut_direction
    del bpy.types.Scene.cut_distance
    del bpy.types.Scene.accordion_change_props
    del bpy.types.Scene.accordion_move_to_origin
    del bpy.types.Scene.accordion_axis_cut