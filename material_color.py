import bpy

def ensure_principled(mat: bpy.types.Material):
    """確保材質節點中有 Principled BSDF，沒有就建立並接到輸出。"""
    mat.use_nodes = True
    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links

    # 找 Principled
    principled = None
    for n in nodes:
        if n.type == 'BSDF_PRINCIPLED':
            principled = n
            break
    # 沒有就加一個
    if not principled:
        principled = nodes.new("ShaderNodeBsdfPrincipled")
        principled.location = (0, 0)

    # 找輸出
    output = None
    for n in nodes:
        if n.type == 'OUTPUT_MATERIAL':
            output = n
            break
    if not output:
        output = nodes.new("ShaderNodeOutputMaterial")
        output.location = (300, 0)

    # 若未連線，連 Principled -> Output
    if not principled.outputs["BSDF"].is_linked:
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    return principled

def apply_viewport_color_to_principled(mat: bpy.types.Material, set_alpha=True):
    """把 Viewport Display 顏色(含透明度)塞到 Principled Base Color / Alpha。"""
    if mat is None:
        return

    # Solid 模式顏色來源：Viewport Display 顏色（material.diffuse_color RGBA）
    # 注意：若你把視窗設定為顯示 Object 顏色，則會來自 obj.color（下方備註有寫）
    r, g, b, a = mat.diffuse_color

    principled = ensure_principled(mat)

    # Base Color 用 RGB，Alpha 另行設定
    principled.inputs["Base Color"].default_value = (r, g, b, 1.0)

    if set_alpha:
        principled.inputs["Alpha"].default_value = a
        # 讓透明度在視窗可見（Eevee）
        mat.blend_method = 'BLEND'      # 也可用 'HASHED' 對半透明陰影友好
        mat.shadow_method = 'HASHED'    # 透明陰影
        mat.use_backface_culling = False
    else:
        principled.inputs["Alpha"].default_value = 1.0
        mat.blend_method = 'OPAQUE'
        mat.shadow_method = 'OPAQUE'

def run_on_selected_objects(use_alpha=True):
    count = 0
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        # 逐個材質槽處理
        if not obj.data.materials:
            continue
        for mat in obj.data.materials:
            if mat:
                apply_viewport_color_to_principled(mat, set_alpha=use_alpha)
                count += 1
    print(f"Updated {count} material(s).")

# 執行：把 Solid 顏色與透明度套到 Principled
run_on_selected_objects(use_alpha=True)
