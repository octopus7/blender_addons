bl_info = {
    "name": "Clip Studio Bridge",
    "author": "BlenG",
    "version": (0, 1, 0),
    "blender": (4, 5, 0),
    "location": "3D Viewport > Sidebar > ClipStudio",
    "description": "Clip Studio 통합을 염두에 둔 기본 애드온 스켈레톤",
    "category": "Import-Export",
}

import bpy
from bpy.types import AddonPreferences, Operator, Panel
from bpy.props import StringProperty, BoolProperty, EnumProperty
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
        name="Clip Studio 경로",
        subtype='FILE_PATH',
        description="Clip Studio 실행 파일 경로",
        default=CSP_DEFAULT_PATH,
    )

    show_path_controls_in_viewport: BoolProperty(
        name="뷰포트에 경로/찾기 표시",
        description="뷰포트 패널에서 CSP 경로와 자동검색 버튼을 표시합니다",
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
                return {
                    'window': window,
                    'screen': screen,
                    'area': area,
                    'region': region,
                    'space_data': space,
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
                return {
                    'window': window,
                    'screen': screen,
                    'area': area,
                    'region': region,
                    'space_data': space,
                }
    return None


def _viewport_render_to_file(context, fmt_code: str, filepath_no_ext: str) -> str:
    scene = context.scene
    img_settings = scene.render.image_settings
    prev_fmt = img_settings.file_format
    prev_path = scene.render.filepath
    # 확장자 맵핑
    want_ext = 'png' if fmt_code == 'PNG' else 'tif'

    ovr = _find_view3d_context(context)
    if not ovr:
        raise RuntimeError("3D Viewport를 찾을 수 없습니다.")

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


def _create_tmp_camera_from_view(ovr):
    scene = bpy.context.scene
    cam_data = bpy.data.cameras.new("CSP_QE_TMP_CAM")
    cam = bpy.data.objects.new("CSP_QE_TMP_CAM", cam_data)
    scene.collection.objects.link(cam)
    vl = bpy.context.view_layer
    prev_active = vl.objects.active
    try:
        vl.objects.active = cam
        with bpy.context.temp_override(**ovr):
            try:
                bpy.ops.view3d.camera_to_view()
            except Exception:
                pass
        scene.camera = cam
    finally:
        if prev_active:
            vl.objects.active = prev_active
    return cam


def _ensure_projector_camera(ovr) -> bpy.types.Object:
    # 씬에 투영용 임시 카메라를 준비하고 현재 뷰에 정렬
    scene = bpy.context.scene
    cam = scene.objects.get("CSP_QuickEditCam")
    if not cam:
        cam_data = bpy.data.cameras.new("CSP_QuickEditCam")
        cam = bpy.data.objects.new("CSP_QuickEditCam", cam_data)
        scene.collection.objects.link(cam)

    # 활성 객체로 설정하고 뷰와 일치하도록 정렬
    view_layer = bpy.context.view_layer
    prev_active = view_layer.objects.active
    try:
        view_layer.objects.active = cam
        with bpy.context.temp_override(**ovr):
            try:
                bpy.ops.view3d.camera_to_view()
            except Exception:
                pass
        scene.camera = cam
    finally:
        if prev_active:
            view_layer.objects.active = prev_active
    return cam


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
    bl_label = "CSP 경로 자동검색"
    bl_description = "시스템에서 Clip Studio Paint 설치 경로를 찾아 설정합니다"

    def execute(self, context):
        prefs = get_prefs()
        if not prefs:
            self.report({'ERROR'}, "애드온 환경설정을 찾을 수 없습니다.")
            return {'CANCELLED'}
        found = detect_csp_path()
        if found:
            prefs.csp_path = found
            self.report({'INFO'}, f"경로 설정: {found}")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "설치 경로를 찾지 못했습니다. 수동으로 지정하세요.")
            return {'CANCELLED'}


# (삭제됨) 임의 파일 열기 오퍼레이터




class CLIPSTUDIO_QUICKEDIT_OT_start(Operator):
    bl_idname = "clipstudio.quickedit_start"
    bl_label = "Quick Edit 시작 (CSP)"
    bl_description = "현재 뷰포트를 캡처하여 CSP로 열고, 원본 텍스처로 되돌아올 투영 정보를 준비합니다"
    bl_options = {'REGISTER'}

    def execute(self, context):
        prefs = get_prefs()
        if not prefs or not prefs.csp_path:
            self.report({'ERROR'}, "CSP 경로가 설정되지 않았습니다. Preferences에서 지정하세요.")
            return {'CANCELLED'}

        dest_img = get_active_image(context)
        if not dest_img:
            self.report({'ERROR'}, "원본이 될 활성 텍스처 이미지가 필요합니다. 이미지 에디터/텍스처 페인트/이미지 텍스처 노드를 확인하세요.")
            return {'CANCELLED'}

        # 3D 뷰 컨텍스트 확보 및 투영 카메라 준비
        ovr = _find_view3d_context(context)
        if not ovr:
            self.report({'ERROR'}, "3D Viewport를 찾을 수 없습니다.")
            return {'CANCELLED'}

        # 뷰포트 캡처
        qdir = _ensure_quickedit_path(prefs)
        name = _sanitize_filename(dest_img.name)
        basename = f"{name}_view_{_timestamp()}"
        filepath_no_ext = os.path.join(qdir, basename)
        try:
            proj_path = _viewport_render_to_file(context, 'PNG', filepath_no_ext)
        except Exception as e:
            self.report({'ERROR'}, f"뷰포트 캡처 실패: {e}")
            return {'CANCELLED'}

        # 캡처 이미지를 블렌더에 로드
        try:
            proj_img = bpy.data.images.load(proj_path, check_existing=True)
        except Exception as e:
            self.report({'ERROR'}, f"캡처 이미지 로드 실패: {e}")
            return {'CANCELLED'}

        # 세션 저장 (키: 대상 텍스처 이미지명)
        _set_session(dest_img, {
            'dest_image_name': dest_img.name,
            'proj_path': proj_path,
            'proj_image_name': proj_img.name,
            'started': _timestamp(),
        })

        ok = launch_csp(prefs.csp_path, proj_path)
        if not ok:
            self.report({'ERROR'}, "CSP 실행 실패: 경로를 확인하세요.")
            return {'CANCELLED'}

        self.report({'INFO'}, "Quick Edit 시작: 뷰포트 캡처를 CSP로 열었습니다.")
        return {'FINISHED'}




class CLIPSTUDIO_QUICKEDIT_OT_finish(Operator):
    bl_idname = "clipstudio.quickedit_finish"
    bl_label = "임시파일 정리"
    bl_description = "Quick Edit 세션을 정리합니다 (선택 시 캡처 파일 삭제)"
    bl_options = {'REGISTER'}

    cleanup_temp: BoolProperty(
        name="임시파일 삭제",
        description="Quick Edit를 위해 생성된 뷰포트 캡처 파일을 삭제합니다",
        default=True,
    )

    def execute(self, context):
        img = get_active_image(context)
        if not img:
            self.report({'ERROR'}, "활성 이미지가 없습니다.")
            return {'CANCELLED'}

        sess = _session_for(img)
        if not sess:
            self.report({'WARNING'}, "활성 세션 정보가 없어 정리할 항목이 없습니다.")
            return {'FINISHED'}

        proj_path = sess.get('proj_path')
        proj_name = sess.get('proj_image_name')

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

        _del_session(img)
        self.report({'INFO'}, "Quick Edit 세션 정리 완료")
        return {'FINISHED'}


class CLIPSTUDIO_QUICKEDIT_OT_apply_projection(Operator):
    bl_idname = "clipstudio.quickedit_apply_projection"
    bl_label = "Apply Projection (Active Obj)"
    bl_description = "CSP에서 저장한 캡처 파일을 다시 읽고, 현재 뷰 기준으로 활성 오브젝트의 텍스처에 투영 적용합니다"

    target: EnumProperty(
        name="대상",
        items=[
            ('ACTIVE', "활성 오브젝트", "활성 오브젝트에만 적용"),
            ('SELECTED', "선택 오브젝트(미사용)", "선택 오브젝트 전체 (향후 확장)")
        ],
        default='ACTIVE',
        options={'HIDDEN'},  # UI는 일단 숨김, 확장 여지만 둠
    )

    def execute(self, context):
        dest_img = get_active_image(context)
        if not dest_img:
            self.report({'ERROR'}, "활성 이미지가 없습니다.")
            return {'CANCELLED'}

        objs = _iter_target_objects(context, self.target)
        if not objs:
            self.report({'ERROR'}, "대상 오브젝트(메시)가 활성화되어 있지 않습니다.")
            return {'CANCELLED'}

        sess = _session_for(dest_img)
        if not sess:
            self.report({'ERROR'}, "Quick Edit 세션이 없습니다. 먼저 Start를 실행하세요.")
            return {'CANCELLED'}

        proj_name = sess.get('proj_image_name')
        src_path = bpy.path.abspath(sess.get('proj_path') or "")
        if not (src_path and os.path.isfile(src_path)):
            self.report({'ERROR'}, "투영할 소스 파일이 없습니다. Quick Edit로 편집/저장 후 다시 시도하세요.")
            return {'CANCELLED'}

        # 소스 이미지를 별도 Image로 로드 (타깃과 동일 경로여도 check_existing으로 참조)
        try:
            src_img = bpy.data.images.get(proj_name) or bpy.data.images.load(src_path, check_existing=True)
            try:
                src_img.reload()
            except Exception:
                pass
        except Exception as e:
            self.report({'ERROR'}, f"소스 이미지 로드 실패: {e}")
            return {'CANCELLED'}

        # 3D Viewport 컨텍스트 확보
        ovr = _find_view3d_context(context)
        if not ovr:
            self.report({'ERROR'}, "3D Viewport를 찾을 수 없습니다.")
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

            # 1) 가능하면 자동 프로젝션 오퍼레이터 사용
            op = getattr(bpy.ops.paint, 'project_image', None)
            if op is not None:
                try:
                    # Texture Paint 모드 필요 시 전환
                    bpy.ops.object.mode_set(mode='TEXTURE_PAINT')
                    # 페인트 캔버스 지정
                    ts = context.tool_settings
                    if ts and ts.image_paint:
                        ts.image_paint.canvas = dest_img
                    with bpy.context.temp_override(**ovr):
                        res = bpy.ops.paint.project_image(image=src_img.name)
                    if res == {'FINISHED'}:
                        return {'FINISHED'}
                except Exception as e:
                    print(f"[ClipStudio] project_image failed: {e}")

            # 2) Fallback: 임시 카메라 + Emission 베이크로 투영 적용
            scene = context.scene
            prev_engine = scene.render.engine
            tmp_cam = None
            tmp_mat = None
            try:
                # 임시 카메라를 현재 뷰에 맞춤
                tmp_cam = _create_tmp_camera_from_view(ovr)
                scene.camera = tmp_cam

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

                self.report({'INFO'}, "프로젝션 적용 완료 (베이크)")
                return {'FINISHED'}
            except Exception as e:
                self.report({'ERROR'}, f"프로젝션 적용 실패: {e}")
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
                if tmp_cam:
                    try:
                        bpy.context.scene.collection.objects.unlink(tmp_cam)
                    except Exception:
                        pass
                    try:
                        bpy.data.objects.remove(tmp_cam, do_unlink=True)
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

        self.report({'INFO'}, "프로젝션 적용 완료 (활성 오브젝트)")
        return {'FINISHED'}


class VIEW3D_PT_csp_quickedit(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "CSP QuickEdit"
    bl_label = "CSP Quick Edit"

    def draw(self, context):
        layout = self.layout
        prefs = get_prefs()
        img = get_active_image(context)

        # 상태/경로 박스
        box = layout.box()
        row = box.row()
        row.label(text="상태", icon='INFO')
        if prefs and prefs.show_path_controls_in_viewport:
            box.prop(prefs, "csp_path")
            box.operator("clipstudio.detect_path", icon='FILE_REFRESH')
        else:
            exe = bpy.path.abspath(prefs.csp_path) if (prefs and prefs.csp_path) else ""
            ok = bool(exe and os.path.isfile(exe))
            if ok:
                box.label(text="사용 가능", icon='CHECKMARK')
            else:
                box.label(text="경로 미설정/실행 파일 없음", icon='ERROR')

        # 활성 이미지 정보
        info = layout.box()
        info.label(text=f"활성 이미지: {img.name if img else '(없음)'}", icon='IMAGE_DATA')
        if img:
            path = bpy.path.abspath(img.filepath_raw or img.filepath)
            info.label(text=f"경로: {path if path else '(임시/메모리)'}")

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
