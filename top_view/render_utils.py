import bpy

def set_viewport_shading(area):
    sh = area.spaces.active.shading
    sh.type = 'SOLID'
    sh.light = 'FLAT'
    sh.color_type = 'SINGLE'
    sh.single_color = (1,1,1)
    sh.background_type = 'VIEWPORT'
    sh.background_color = (1,1,1)
    sh.show_object_outline = True
    sh.object_outline_color = (0,0,0)
    sh.show_cavity = True
    sh.cavity_type = 'BOTH'
    sh.cavity_ridge_factor = 1.2
    sh.cavity_valley_factor = 1.2
    sh.show_xray = False
    sh.show_shadows = False

def set_render_settings(scn, width, height, engine='BLENDER_WORKBENCH'):
    scn.render.engine = engine
    scn.view_settings.view_transform = 'Standard'
    scn.view_settings.look = 'High Contrast'
    scn.render.resolution_x = width
    scn.render.resolution_y = height
    scn.render.resolution_percentage = 100