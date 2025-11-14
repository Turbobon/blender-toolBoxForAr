"""Tools for renaming IFC element names based on their IDs.

This module provides operators and panels that allow users to batch rename
IFC elements by appending their Tag to the Name field, which can be useful
when preparing models for AR applications.
"""

import os
import bpy


def update_ifc_output(self, context):
    """Automatically update output path when input path changes."""
    input_path = self.ar_ifc_input_path
    if input_path:
        name, ext = os.path.splitext(input_path)
        # 預設輸出檔案為原檔名加上 _id 後綴
        context.scene.ar_ifc_output_path = name + "_id" + ext


def name_ifc_elements_by_tag(ifcopenshell, file_path, output_path, prefix):
    """Rename IFC elements using their Tag property.

    Parameters
    ----------
    ifcopenshell : module
        Imported ifcopenshell module used to open and manipulate IFC data.
    file_path : str
        Path to the input IFC file.
    output_path : str
        Path where the renamed IFC will be written.
    prefix : str
        Optional prefix appended before each Tag.
    """
    if prefix != '':
        prefix = f'{prefix}_'
    ifc = ifcopenshell.open(file_path)
    # 指定需要處理的 IFC 元件類型
    listType = [
        'IfcColumn', 'IfcCurtainWall', 'IfcWall', 'IfcWallStandardCase',
        'IfcFlowFitting', 'IfcFlowSegment', 'IfcFlowTerminal',
        'IfcDistributionControlElement', 'IfcFlowController',
        'IfcFurnishingElement', 'IfcPlate', 'IfcSlab', 'IfcDoor',
        'IfcBuildingElementProxy', 'IfcStair', 'IfcBeam', 'IfcStairFlight',
        'IfcMember', 'IfcCovering', 'IfcWindow'
    ]
    # 迭代所有指定類型並改名
    for type_name in listType:
        for ele in ifc.by_type(type_name):
            ele.Name = f'{prefix}{ele.Tag}'
    ifc.write(output_path)


class OBJECT_OT_rename_ifc_elements(bpy.types.Operator):
    """Rename a single IFC file's elements using their Tag values."""

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
        # 執行實際的改名流程
        name_ifc_elements_by_tag(ifcopenshell, file_path, export_file_name, prefix)

        self.report({'INFO'}, f"已產出新 IFC：{export_file_name}")
        return {'FINISHED'}


class OBJECT_OT_batch_rename_ifc_folder(bpy.types.Operator):
    """Rename all IFC files within a folder."""

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
                    output_path = os.path.join(root, os.path.splitext(file)[0] + "_id.ifc")
                    try:
                        prefix = os.path.splitext(file)[0] if use_prefix else ""
                        # 對每個檔案進行改名
                        name_ifc_elements_by_tag(ifcopenshell, input_path, output_path, prefix)
                        count += 1
                    except Exception as e:
                        self.report({'WARNING'}, f"{file} 轉換失敗：{e}")

        self.report({'INFO'}, f"已處理 {count} 個 IFC 檔案，輸出至原資料夾中")
        return {'FINISHED'}


class OBJECT_PT_rename_ifc(bpy.types.Panel):
    """User interface for the IFC renaming operations."""

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


classes = (
    OBJECT_OT_rename_ifc_elements,
    OBJECT_OT_batch_rename_ifc_folder,
    OBJECT_PT_rename_ifc,
)


def register():
    """Register operator classes and scene properties."""
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.ar_ifc_input_path = bpy.props.StringProperty(
        name="Input",
        subtype='FILE_PATH',
        update=update_ifc_output,
    )
    bpy.types.Scene.ar_ifc_output_path = bpy.props.StringProperty(
        name="Output",
        subtype='FILE_PATH',
    )
    bpy.types.Scene.ar_ifc_prefix = bpy.props.StringProperty(
        name="Prefix",
        description="Prefix for renaming elements",
        default="",
    )
    bpy.types.Scene.use_filename_as_prefix = bpy.props.BoolProperty(
        name="Use FileName as Prefix",
        description="Use IFC FileName as Elements Prefix",
        default=True,
    )
    bpy.types.Scene.ar_ifc_folder_path = bpy.props.StringProperty(
        name="Folder",
        subtype='FILE_PATH',
    )


def unregister():
    """Unregister classes and remove custom properties."""
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.ar_ifc_input_path
    del bpy.types.Scene.ar_ifc_output_path
    del bpy.types.Scene.ar_ifc_prefix
    del bpy.types.Scene.use_filename_as_prefix
    del bpy.types.Scene.ar_ifc_folder_path
