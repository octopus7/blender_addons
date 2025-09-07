bl_info = {
    "name": "Clip Studio Bridge",
    "author": "BlenG",
    "version": (0, 1, 0),
    "blender": (4, 5, 0),
    "location": "3D Viewport > Sidebar > Clip Studio Bridge",
    "description": "Capture the current viewport to Clip Studio Paint and project the edited result back onto the active object's texture (Windows first).",
    "category": "Import-Export",
}

import bpy
from bpy.types import AddonPreferences, Operator, Panel
from bpy.props import StringProperty, BoolProperty, EnumProperty
from mathutils import Matrix
import os
import sys
import subprocess
import shutil
from datetime import datetime

# --------------------
# Defaults / Globals
# --------------------

def _guess_csp_default() -> str:
    # Windows 우선 기본값 (타 OS는 빈 값으로 확장 대기)
    if sys.platform.startswith('win'):
        for p in (
            r"C:\\Program Files\\CELSYS\\CLIP STUDIO\\CLIP STUDIO PAINT\\CLIPStudioPaint.exe",
            r"C:\\Program Files\\CELSYS\\CLIP STUDIO 1.5\\CLIP STUDIO PAINT\\CLIPStudioPaint.exe",
            r"C:\\Program Files (x86)\\CELSYS\\CLIP STUDIO 1.5\\CLIP STUDIO PAINT\\CLIPStudioPaint.exe",
        ):
            if os.path.isfile(p):
                return p
        # 최빈 경로를 기본값으로 설정 (없어도 기본값으로 노출)
        return r"C:\\Program Files\\CELSYS\\CLIP STUDIO\\CLIP STUDIO PAINT\\CLIPStudioPaint.exe"
    return ""

CSP_DEFAULT_PATH = _guess_csp_default()

# Quick Edit 세션 관리 (이미지명 -> 정보)
_quick_sessions = {}


def get_prefs():
    name = __package__ or __name__
    addon = bpy.context.preferences.addons.get(name)
    return addon.preferences if addon else None


class CLIPSTUDIO_Preferences(AddonPreferences):
    bl_idname = __package__ or __name__

    csp_path: StringProperty(
        name="Clip Studio Path",
        subtype='FILE_PATH',
        description="Path to Clip Studio Paint executable",
        default=CSP_DEFAULT_PATH,
    )

    show_path_controls_in_viewport: BoolProperty(
        name="Show Path Controls in Viewport",
        description="Show CSP path and detect button in the viewport panel",
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "csp_path")
        col.prop(self, "show_path_controls_in_viewport")
        col.operator("clipstudio.detect_path", icon='FILE_REFRESH')


# --------------------
# OS/Path helpers
# --------------------

def _is_windows():
    return sys.platform.startswith('win')


def _is_mac():
    return sys.platform == 'darwin'


def _is_linux():
    return sys.platform.startswith('linux')


def detect_csp_path() -> str:
    # Windows 우선: 대표 설치 경로만 검색 (확장 용이하게 유지)
    if _is_windows():
        candidates = [
            r"C:\\Program Files\\CELSYS\\CLIP STUDIO\\CLIP STUDIO PAINT\\CLIPStudioPaint.exe",
            r"C:\\Program Files\\CELSYS\\CLIP STUDIO 1.5\\CLIP STUDIO PAINT\\CLIPStudioPaint.exe",
            r"C:\\Program Files (x86)\\CELSYS\\CLIP STUDIO 1.5\\CLIP STUDIO PAINT\\CLIPStudioPaint.exe",
            r"C:\\Program Files\\CELSYS\\CLIP STUDIO PAINT\\CLIPStudioPaint.exe",
        ]
        for p in candidates:
            if os.path.isfile(p):
                return p
    # 그 외 OS는 현재 자동검색 미지원
    return ""


def _ensure_dir(path: str):
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)


def launch_csp(csp_path: str, file_to_open: str | None = None) -> bool:
    if not csp_path:
        return False
    try:
        exe = bpy.path.abspath(csp_path)
        args = [exe]
        if file_to_open:
            args.append(bpy.path.abspath(file_to_open))
        subprocess.Popen(args)
        return True
    except Exception as e:
        print(f"[ClipStudio] Failed to launch: {e}")
        return False


def _default_export_dir(prefs: CLIPSTUDIO_Preferences | None) -> str:
    # UI에서 경로를 받지 않으므로 Blender의 임시 폴더를 기본 사용
    base = bpy.app.tempdir
    if not base:
        base = os.path.expanduser("~")
    path = os.path.join(base, "clipstudio")
    _ensure_dir(path)
    return path


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _sanitize_filename(name: str) -> str:
    bad = '<>:"/\\|?*\n\r\t'
    cleaned = ''.join('_' if c in bad else c for c in name)
    return cleaned.strip().strip('.') or 'image'


def get_active_image(context) -> bpy.types.Image | None:
    # 우선순위 1: 텍스처 페인트 캔버스
    ts = context.tool_settings if context else None
    if ts and ts.image_paint:
        canvas = ts.image_paint.canvas
        if canvas:
            return canvas

    # 우선순위 2: 열려있는 이미지 에디터의 이미지
    try:
        for area in context.window.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                sp = area.spaces.active
                if sp and getattr(sp, 'image', None):
                    img = sp.image
                    if img:
                        return img
    except Exception:
        pass

    # 우선순위 3: 활성 머티리얼의 활성 이미지 텍스처 노드
    ob = context.active_object
    if ob and ob.active_material and ob.active_material.use_nodes:
        nt = ob.active_material.node_tree
        if nt and nt.nodes.active and nt.nodes.active.type == 'TEX_IMAGE':
            node = nt.nodes.active
            if node.image:
                return node.image

    # fallback: 없음
    return None


def _image_has_file(img: bpy.types.Image) -> bool:
    if not img:
        return False
    fp = bpy.path.abspath(img.filepath_raw or img.filepath)
    return bool(fp and os.path.isfile(fp))


def _ensure_quickedit_path(prefs) -> str:
    base = _default_export_dir(prefs)
    qd = os.path.join(base, 'quickedit')
    _ensure_dir(qd)
    return qd


def _find_view3d_context(ctx=None):
    # 1) 우선, 현재 버튼을 누른 뷰포트 컨텍스트를 사용
    if ctx is None:
        ctx = bpy.context
    try:
        area = getattr(ctx, 'area', None)
        if area and area.type == 'VIEW_3D':
            window = getattr(ctx, 'window', None)
            screen = window.screen if window else None
            region = None
            for r in area.regions:
                if r.type == 'WINDOW':
                    region = r
                    break
            if window and screen and region:
                space = area.spaces.active if area.spaces else None
                region_3d = getattr(space, 'region_3d', None) if space else None
                return {
                    'window': window,
                    'screen': screen,
                    'area': area,
                    'region': region,
                    'space_data': space,
                    'region_3d': region_3d,
                }
    except Exception:
        pass

    # 2) 실패 시, 첫 번째 3D Viewport를 검색하여 사용
    wm = bpy.context.window_manager
    if not wm:
        return None
    for window in wm.windows:
        screen = window.screen
        if not screen:
            continue
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                region = None
                for r in area.regions:
                    if r.type == 'WINDOW':
                        region = r
                        break
                if not region:
                    continue
                space = area.spaces.active if area.spaces else None
                region_3d = getattr(space, 'region_3d', None) if space else None
                return {
                    'window': window,
                    'screen': screen,
                    'area': area,
                    'region': region,
                    'space_data': space,
                    'region_3d': region_3d,
                }


def _override_from_view3d(vctx: dict) -> dict:
    if not vctx:
        return {}
    ovr = {
        'window': vctx.get('window'),
        'screen': vctx.get('screen'),
        'area': vctx.get('area'),
        'region': vctx.get('region'),
        'space_data': vctx.get('space_data'),
        # Blender가 기대하는 키는 region_data이며, space.region_3d를 전달해야 현재 뷰 행렬을 정확히 사용합니다.
        'region_data': vctx.get('region_3d'),
    }
    return ovr
    return None


def _viewport_render_to_file(context, fmt_code: str, filepath_no_ext: str) -> str:
    scene = context.scene
    img_settings = scene.render.image_settings
    prev_fmt = img_settings.file_format
    prev_path = scene.render.filepath
    # 확장자 맵핑
    want_ext = 'png' if fmt_code == 'PNG' else 'tif'

    vctx = _find_view3d_context(context)
    ovr = _override_from_view3d(vctx)
    if not ovr:
        raise RuntimeError("3D Viewport not found.")

    try:
        img_settings.file_format = fmt_code
        scene.render.filepath = filepath_no_ext
        # viewport 기준 OpenGL 렌더를 파일로 저장
        with bpy.context.temp_override(**ovr):
            bpy.ops.render.opengl(view_context=True, write_still=True)
    finally:
        scene.render.filepath = prev_path
        img_settings.file_format = prev_fmt

    # Blender가 붙여 저장한 최종 경로 추정
    cand1 = filepath_no_ext + "." + want_ext
    cand2 = filepath_no_ext + ".tiff"
    if os.path.isfile(cand1):
        return cand1
    if os.path.isfile(cand2):
        return cand2
    # 마지막 수단: 파일 존재 여부 무시하고 cand1 반환
    return cand1


def _create_tmp_camera_from_view(vctx, name: str = None):
    scene = bpy.context.scene
    cam_name = name or "CSP_QE_TMP_CAM"
    cam_data = bpy.data.cameras.new(cam_name)
    cam = bpy.data.objects.new(cam_name, cam_data)
    scene.collection.objects.link(cam)
    vl = bpy.context.view_layer
    prev_active = vl.objects.active
    try:
        vl.objects.active = cam
        # Align camera to current view matrices directly
        try:
            r3d = vctx.get('region_3d') if vctx else None
            space = vctx.get('space_data') if vctx else None
            if r3d:
                cam.matrix_world = r3d.view_matrix.inverted()
            cam.data.type = 'PERSP'
            if space and hasattr(space, 'lens'):
                cam.data.lens = space.lens
            vp = getattr(r3d, 'view_perspective', None) if r3d else None
            print(f"[ClipStudio] Created temp camera {cam.name}, view_persp={vp}, lens={getattr(space,'lens',None)}")
        except Exception:
            pass
        try:
            scene.camera = cam
        except Exception:
            pass
    finally:
        if prev_active:
            vl.objects.active = prev_active
    return cam


# (removed) legacy ensure camera via operator


def _session_for(img: bpy.types.Image):
    return _quick_sessions.get(img.name)


def _set_session(img: bpy.types.Image, data: dict):
    _quick_sessions[img.name] = data


def _del_session(img: bpy.types.Image):
    _quick_sessions.pop(img.name, None)


def _iter_target_objects(context, target: str = 'ACTIVE'):
    if target == 'SELECTED':
        return [ob for ob in (context.selected_objects or []) if ob and ob.type == 'MESH']
    ob = context.active_object
    return [ob] if (ob and ob.type == 'MESH') else []


# (삭제됨) 테스트용 헬로 오퍼레이터


class CLIPSTUDIO_OT_detect_path(Operator):
    bl_idname = "clipstudio.detect_path"
    bl_label = "Detect CSP Path"
    bl_description = "Find Clip Studio Paint installation path and set it"

    def execute(self, context):
        prefs = get_prefs()
        if not prefs:
            self.report({'ERROR'}, "Add-on preferences not found.")
            return {'CANCELLED'}
        found = detect_csp_path()
        if found:
            prefs.csp_path = found
            self.report({'INFO'}, f"Path set: {found}")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "Installation not found. Please set manually.")
            return {'CANCELLED'}


# (삭제됨) 임의 파일 열기 오퍼레이터




class CLIPSTUDIO_QUICKEDIT_OT_start(Operator):
    bl_idname = "clipstudio.quickedit_start"
    bl_label = "Start Quick Edit (CSP)"
    bl_description = "Capture current viewport to CSP and prepare projection back to the active texture"
    bl_options = {'REGISTER'}

    def execute(self, context):
        prefs = get_prefs()
        if not prefs or not prefs.csp_path:
            self.report({'ERROR'}, "CSP path is not set. Set it in Preferences.")
            return {'CANCELLED'}

        dest_img = get_active_image(context)
        if not dest_img:
            self.report({'ERROR'}, "No active texture image. Select one in Image Editor/Texture Paint/Active Image Texture node.")
            return {'CANCELLED'}

        # 3D 뷰 컨텍스트 확보 및 투영 카메라 준비
        vctx = _find_view3d_context(context)
        ovr = _override_from_view3d(vctx)
        if not ovr:
            self.report({'ERROR'}, "3D Viewport not found.")
            return {'CANCELLED'}

        # 뷰포트 캡처 및 현재 뷰 기준 임시 카메라 생성(Apply 때 사용 후 제거)
        cam = None
        prev_cam_name = bpy.context.scene.camera.name if (bpy.context.scene and bpy.context.scene.camera) else ""
        qdir = _ensure_quickedit_path(prefs)
        name = _sanitize_filename(dest_img.name)
        basename = f"{name}_view_{_timestamp()}"
        filepath_no_ext = os.path.join(qdir, basename)
        try:
            proj_path = _viewport_render_to_file(context, 'PNG', filepath_no_ext)
            # 카메라 생성은 캡처 직후에 수행
            cam = _create_tmp_camera_from_view(vctx, name=f"CSP_QE_CAM_{_timestamp()}")
        except Exception as e:
            self.report({'ERROR'}, f"Viewport capture failed: {e}")
            return {'CANCELLED'}

        # 캡처 이미지를 블렌더에 로드
        try:
            proj_img = bpy.data.images.load(proj_path, check_existing=True)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load capture image: {e}")
            return {'CANCELLED'}

        # 세션 저장 (키: 대상 텍스처 이미지명)
        _set_session(dest_img, {
            'dest_image_name': dest_img.name,
            'proj_path': proj_path,
            'proj_image_name': proj_img.name,
            'started': _timestamp(),
            'cam_name': cam.name if cam else "",
            'prev_cam_name': prev_cam_name,
        })

        ok = launch_csp(prefs.csp_path, proj_path)
        if not ok:
            self.report({'ERROR'}, "Failed to launch CSP. Check the path.")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Quick Edit started: opened capture in CSP, created camera {cam.name if cam else 'N/A'}")
        return {'FINISHED'}




class CLIPSTUDIO_QUICKEDIT_OT_finish(Operator):
    bl_idname = "clipstudio.quickedit_finish"
    bl_label = "Clean Temporary Files"
    bl_description = "Clean up Quick Edit session (optionally delete capture file)"
    bl_options = {'REGISTER'}

    cleanup_temp: BoolProperty(
        name="Delete Temporary File",
        description="Delete the viewport capture image created for Quick Edit",
        default=True,
    )

    def execute(self, context):
        img = get_active_image(context)
        if not img:
            self.report({'ERROR'}, "No active image.")
            return {'CANCELLED'}

        sess = _session_for(img)
        if not sess:
            self.report({'WARNING'}, "No active session to clean.")
            return {'FINISHED'}

        proj_path = sess.get('proj_path')
        proj_name = sess.get('proj_image_name')
        cam_name = sess.get('cam_name')

        # 임시 파일 정리 (선택)
        if self.cleanup_temp and proj_path and os.path.isfile(proj_path):
            try:
                os.remove(proj_path)
            except Exception:
                pass

        # 로드된 캡처 이미지가 있다면 재로드로 동기화만 보장
        if proj_name and bpy.data.images.get(proj_name):
            try:
                bpy.data.images[proj_name].reload()
            except Exception:
                pass

        # 세션 동안 생성된 카메라 정리 및 이전 카메라 복원
        prev_cam_name = sess.get('prev_cam_name')
        prev_cam = bpy.data.objects.get(prev_cam_name) if prev_cam_name else None
        if cam_name:
            cam = bpy.context.scene.objects.get(cam_name) or bpy.data.objects.get(cam_name)
            if cam:
                # 복원: 현재 씬 카메라가 임시카메라면 이전 카메라로 교체
                cur = bpy.context.scene.camera if bpy.context.scene else None
                if cur and cur.name == cam.name:
                    try:
                        bpy.context.scene.camera = prev_cam if prev_cam else None
                    except Exception:
                        pass
                try:
                    bpy.context.scene.collection.objects.unlink(cam)
                except Exception:
                    pass
                try:
                    bpy.data.objects.remove(cam, do_unlink=True)
                except Exception:
                    pass

        _del_session(img)
        self.report({'INFO'}, "Quick Edit session cleaned")
        return {'FINISHED'}


class CLIPSTUDIO_QUICKEDIT_OT_apply_projection(Operator):
    bl_idname = "clipstudio.quickedit_apply_projection"
    bl_label = "Apply Projection (Active Obj)"
    bl_description = "Reload CSP-edited capture and project it onto the active object's texture from current view"

    target: EnumProperty(
        name="Target",
        items=[
            ('ACTIVE', "Active Object", "Apply to active object only"),
            ('SELECTED', "Selected Objects (N/A)", "Apply to selected objects (future)")
        ],
        default='ACTIVE',
        options={'HIDDEN'},
    )

    def execute(self, context):
        dest_img = get_active_image(context)
        if not dest_img:
            self.report({'ERROR'}, "No active image.")
            return {'CANCELLED'}

        objs = _iter_target_objects(context, self.target)
        if not objs:
            self.report({'ERROR'}, "No active mesh object.")
            return {'CANCELLED'}

        sess = _session_for(dest_img)
        if not sess:
            self.report({'ERROR'}, "No Quick Edit session. Run Start first.")
            return {'CANCELLED'}

        proj_name = sess.get('proj_image_name')
        src_path = bpy.path.abspath(sess.get('proj_path') or "")
        if not (src_path and os.path.isfile(src_path)):
            self.report({'ERROR'}, "Source capture not found. Edit/Save in CSP then retry.")
            return {'CANCELLED'}

        # 소스 이미지를 별도 Image로 로드 (타깃과 동일 경로여도 check_existing으로 참조)
        try:
            src_img = bpy.data.images.get(proj_name) or bpy.data.images.load(src_path, check_existing=True)
            try:
                src_img.reload()
            except Exception:
                pass
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load source image: {e}")
            return {'CANCELLED'}

        # 3D Viewport 컨텍스트 확보
        vctx = _find_view3d_context(context)
        ovr = _override_from_view3d(vctx)
        if not ovr:
            self.report({'ERROR'}, "3D Viewport not found.")
            return {'CANCELLED'}

        # 카메라 전환 없이 현재 뷰포트 시점 그대로 사용

        view_layer = context.view_layer
        prev_active = view_layer.objects.active
        prev_modes = {}

        def _set_active(ob):
            if view_layer.objects.active is not ob:
                view_layer.objects.active = ob

        try:
            # 우선 활성 오브젝트만 처리 (확장 여지 유지)
            target_ob = objs[0]
            _set_active(target_ob)
            prev_modes[target_ob.name] = target_ob.mode
            if target_ob.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')

            # 임시 카메라 + Emission 베이크로 투영 적용 (일관 경로)
            scene = context.scene
            prev_engine = scene.render.engine
            tmp_cam = None
            tmp_mat = None
            try:
                # Start에서 생성한 카메라가 있으면 우선 사용, 없으면 즉석 생성
                cam_name = sess.get('cam_name')
                cam = bpy.context.scene.objects.get(cam_name) if cam_name else None
                created_now = False
                if cam is None:
                    cam = _create_tmp_camera_from_view(vctx)
                    created_now = True
                scene.camera = cam

                # 임시 머티리얼 구성 (Window 좌표 → 소스 이미지 → Emission)
                tmp_mat = bpy.data.materials.new(name="CSP_QE_TMP_MAT")
                tmp_mat.use_nodes = True
                nt = tmp_mat.node_tree
                for n in nt.nodes:
                    nt.nodes.remove(n)
                out = nt.nodes.new('ShaderNodeOutputMaterial')
                emis = nt.nodes.new('ShaderNodeEmission')
                img_src = nt.nodes.new('ShaderNodeTexImage')
                img_src.image = src_img
                img_src.interpolation = 'Linear'
                img_src.extension = 'CLIP'
                texcoord = nt.nodes.new('ShaderNodeTexCoord')
                mapping = nt.nodes.new('ShaderNodeMapping')
                # V 뒤집기 보정 (Window 좌표의 Y축 반전)
                mapping.inputs['Scale'].default_value[1] = -1.0
                mapping.inputs['Location'].default_value[1] = 1.0
                nt.links.new(texcoord.outputs['Window'], mapping.inputs['Vector'])
                nt.links.new(mapping.outputs['Vector'], img_src.inputs['Vector'])
                nt.links.new(img_src.outputs['Color'], emis.inputs['Color'])
                nt.links.new(emis.outputs['Emission'], out.inputs['Surface'])

                # 베이크 타깃 이미지 노드 추가 및 활성화
                img_dst = nt.nodes.new('ShaderNodeTexImage')
                img_dst.image = dest_img
                for n in nt.nodes:
                    n.select = False
                img_dst.select = True
                nt.nodes.active = img_dst

                # 대상 오브젝트에 임시 머티리얼 단일 할당
                original_mats = [s.material for s in target_ob.material_slots]
                target_ob.data.materials.clear()
                target_ob.data.materials.append(tmp_mat)

                # Cycles로 전환 후 Bake(EMIT)
                scene.render.engine = 'CYCLES'
                # 선택 상태 정리
                for ob in bpy.context.view_layer.objects:
                    ob.select_set(False)
                target_ob.select_set(True)
                _set_active(target_ob)
                bpy.ops.object.bake(type='EMIT', margin=2, use_clear=False)

                # 베이크 결과는 이미지 데이터에 즉시 반영됨. reload는 메모리 변경을 덮어쓸 수 있으므로 호출하지 않음.

                # 원복
                target_ob.data.materials.clear()
                for m in original_mats:
                    if m:
                        target_ob.data.materials.append(m)

                self.report({'INFO'}, "Projection applied (Bake)")
                return {'FINISHED'}
            except Exception as e:
                self.report({'ERROR'}, f"Projection failed: {e}")
                return {'CANCELLED'}
            finally:
                # 카메라/머티리얼/렌더 엔진 원복 및 정리
                try:
                    scene.render.engine = prev_engine
                except Exception:
                    pass
                if tmp_mat:
                    try:
                        bpy.data.materials.remove(tmp_mat, do_unlink=True)
                    except Exception:
                        pass
                # Start에서 만든 카메라 또는 이번에 생성한 카메라 정리 및 이전 카메라 복원
                prev_cam_name = sess.get('prev_cam_name') if sess else None
                prev_cam = bpy.data.objects.get(prev_cam_name) if prev_cam_name else None
                # 우선 현재 scene.camera가 임시카메라라면 이전 카메라로 복원
                cur_cam = bpy.context.scene.camera if bpy.context.scene else None
                if cur_cam and cur_cam.name.startswith('CSP_QE_CAM'):
                    try:
                        bpy.context.scene.camera = prev_cam if prev_cam else None
                    except Exception:
                        pass
                    try:
                        bpy.context.scene.collection.objects.unlink(cur_cam)
                    except Exception:
                        pass
                    try:
                        bpy.data.objects.remove(cur_cam, do_unlink=True)
                    except Exception:
                        pass
        finally:
            # 모드/활성 복원
            for name, mode in prev_modes.items():
                ob = bpy.data.objects.get(name)
                if ob and ob.mode != mode:
                    try:
                        bpy.ops.object.mode_set(mode=mode)
                    except Exception:
                        pass
            if prev_active:
                try:
                    view_layer.objects.active = prev_active
                except Exception:
                    pass

        self.report({'INFO'}, "Projection applied (Active Object)")
        return {'FINISHED'}


class VIEW3D_PT_csp_quickedit(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Clip Studio Bridge"
    bl_label = "ClipStudio Bridge"

    def draw(self, context):
        layout = self.layout
        prefs = get_prefs()
        img = get_active_image(context)

        # 상태/경로 박스
        box = layout.box()
        row = box.row()
        row.label(text="Status", icon='INFO')
        if prefs and prefs.show_path_controls_in_viewport:
            box.prop(prefs, "csp_path")
            box.operator("clipstudio.detect_path", icon='FILE_REFRESH')
        else:
            exe = bpy.path.abspath(prefs.csp_path) if (prefs and prefs.csp_path) else ""
            ok = bool(exe and os.path.isfile(exe))
            if ok:
                box.label(text="Available", icon='CHECKMARK')
            else:
                box.label(text="Path not set / Executable missing", icon='ERROR')

        # 활성 이미지 정보
        info = layout.box()
        info.label(text=f"Active Image: {img.name if img else '(None)'}", icon='IMAGE_DATA')
        if img:
            path = bpy.path.abspath(img.filepath_raw or img.filepath)
            info.label(text=f"Path: {path if path else '(temp/memory)'}")

        layout.separator()
        col = layout.column(align=True)
        # (정리) 렌더를 CSP로 열기 제거, Start만 사용

        layout.separator()
        col2 = layout.column(align=True)
        col2.operator("clipstudio.quickedit_start", icon='EXPORT')
        col2.operator("clipstudio.quickedit_apply_projection", icon='MOD_UVPROJECT')
        col2.operator("clipstudio.quickedit_finish", icon='TRASH')




classes = (
    CLIPSTUDIO_Preferences,
    CLIPSTUDIO_OT_detect_path,
    CLIPSTUDIO_QUICKEDIT_OT_start,
    CLIPSTUDIO_QUICKEDIT_OT_apply_projection,
    CLIPSTUDIO_QUICKEDIT_OT_finish,
    VIEW3D_PT_csp_quickedit,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    print("[ClipStudio] Registered")


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    print("[ClipStudio] Unregistered")
