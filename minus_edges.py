import bpy
import bmesh

# === 參數 ===
FACE_MIN   = 500          # 只處理面數大於這個值的物件
EDGE_LEN   = 0.01         # 小於此長度的 edge 會被 collapse
MERGE_DIST = 0.0005       # 近點合併距離（等同 Merge by Distance）

# 確保在 Object Mode
if bpy.context.mode != 'OBJECT':
    try:
        bpy.ops.object.mode_set(mode='OBJECT')
    except:
        pass

processed = 0

for obj in bpy.context.scene.objects:
    if obj.type != 'MESH':
        continue
    if len(obj.data.polygons) <= FACE_MIN:
        continue

    bm = bmesh.new()
    bm.from_mesh(obj.data)

    pre_faces = len(bm.faces)
    pre_edges = len(bm.edges)
    pre_verts = len(bm.verts)

    # 1) 近點合併（Merge by Distance）
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DIST)

    # 2) 找出短邊並 collapse（注意：正確的 operator 是 bmesh.ops.collapse）
    short_edges = [e for e in bm.edges
                   if (e.verts[0].co - e.verts[1].co).length < EDGE_LEN]
    if short_edges:
        # 盡量保留 UV；部分版本沒有 uvs 參數也沒關係
        try:
            bmesh.ops.collapse(bm, edges=short_edges, uvs=True)
        except TypeError:
            bmesh.ops.collapse(bm, edges=short_edges)

    # 3) 刪掉鬆散頂點（沒有連結任何邊）
    loose_verts = [v for v in bm.verts if not v.link_edges]
    if loose_verts:
        bmesh.ops.delete(bm, geom=loose_verts, context='VERTS')

    # 4) 重算法線
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    # 寫回 mesh
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

    processed += 1
    print(f"{obj.name}: Faces {pre_faces}->{len(obj.data.polygons)}, "
          f"Edges {pre_edges}->{len(obj.data.edges)}, "
          f"Collapsed {len(short_edges)}")

print(f"完成處理 {processed} 個物件（條件：faces > {FACE_MIN}）。")
