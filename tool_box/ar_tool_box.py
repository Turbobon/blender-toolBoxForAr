"""Add-on entry point that aggregates all AR Tool Box modules.

This file keeps the top-level registration logic lightweight and simply
delegates work to the individual feature modules defined in this
repository.
"""

bl_info = {
    "name": "AR Tool Box",
    "author": "Bimfm_Annie Sung",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > AR Tool Box",
    "description": "Includes Z Rotation Tool and IFC ElementId Renamer",
    "category": "Object",
}

import importlib

import z_rotation_tool  # Z 軸旋轉工具
import ifc_rename_tool  # IFC 元件重新命名工具
import utilities_tool   # 多項實用工具集合

modules = [z_rotation_tool, ifc_rename_tool, utilities_tool]


def register():
    """Reload and register all feature modules."""
    for module in modules:
        # 確保開發時修改可以即時生效
        importlib.reload(module)
        module.register()


def unregister():
    """Unregister feature modules in reverse order."""
    for module in reversed(modules):
        module.unregister()
