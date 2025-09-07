bl_info = {
    "name": "Clip Studio Bridge",
    "author": "blendue",
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

    auto_export: BoolProperty(
        name="자동 내보내기",
        description="작업 시 자동으로 내보내기 동작을 수행",
        default=False,
    )

    export_dir: StringProperty(
        name="내보내기 폴더",
        subtype='DIR_PATH',
        description="렌더 결과를 임시 저장할 폴더 (비우면 임시폴더)",
        default="",
    )

    export_format: EnumProperty(
        name="포맷",
        description="렌더 결과 저장 포맷",
        items=[
            ("PNG", "PNG", "PNG 포맷으로 저장"),
            ("TIFF", "TIFF", "TIFF 포맷으로 저장"),
        ],
        default="PNG",
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "csp_path")
        col.prop(self, "auto_export")
        col.prop(self, "export_dir")
        col.prop(self, "export_format")
        col.operator("clipstudio.detect_path", icon='VIEWZOOM')


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
    base = bpy.path.abspath(prefs.export_dir) if (prefs and prefs.export_dir) else bpy.app.tempdir
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


def _find_view3d_context():
    wm = bpy.context.window_manager
    if not wm:
        return None
    for window in wm.windows:
        screen = window.screen
        if not screen:
            continue
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                # WINDOW 타입 리전 탐색
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

    ovr = _find_view3d_context()
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


def _session_for(img: bpy.types.Image):
    return _quick_sessions.get(img.name)


def _set_session(img: bpy.types.Image, data: dict):
    _quick_sessions[img.name] = data


def _del_session(img: bpy.types.Image):
    _quick_sessions.pop(img.name, None)


class CLIPSTUDIO_OT_hello(Operator):
    bl_idname = "clipstudio.hello"
    bl_label = "Say Hello"
    bl_description = "애드온 동작 테스트"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        self.report({'INFO'}, "ClipStudio Add-on is working!")
        print("[ClipStudio] Hello from the add-on")
        return {'FINISHED'}


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


class CLIPSTUDIO_OT_open_file(Operator):
    bl_idname = "clipstudio.open_file"
    bl_label = "파일을 CSP로 열기"
    bl_description = "선택한 파일을 Clip Studio Paint로 엽니다"

    filepath: StringProperty(name="File Path", subtype='FILE_PATH')
    filter_glob: StringProperty(
        default="*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.bmp;*.psd;*.clip",
        options={'HIDDEN'},
    )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        prefs = get_prefs()
        if not prefs or not prefs.csp_path:
            self.report({'ERROR'}, "CSP 경로가 설정되지 않았습니다. Preferences에서 지정하세요.")
            return {'CANCELLED'}
        if not self.filepath:
            self.report({'ERROR'}, "파일이 선택되지 않았습니다.")
            return {'CANCELLED'}
        ok = launch_csp(prefs.csp_path, self.filepath)
        if not ok:
            self.report({'ERROR'}, "CSP 실행에 실패했습니다. 경로를 확인하세요.")
            return {'CANCELLED'}
        return {'FINISHED'}


class CLIPSTUDIO_OT_export_render_open(Operator):
    bl_idname = "clipstudio.export_render_open"
    bl_label = "렌더를 CSP로 열기"
    bl_description = "현재 씬을 렌더링하여 저장 후 Clip Studio Paint로 엽니다"
    bl_options = {'REGISTER'}

    def execute(self, context):
        prefs = get_prefs()
        if not prefs or not prefs.csp_path:
            self.report({'ERROR'}, "CSP 경로가 설정되지 않았습니다. Preferences에서 지정하세요.")
            return {'CANCELLED'}

        export_dir = _default_export_dir(prefs)
        fmt_code = (prefs.export_format or 'PNG')
        ext = 'png' if fmt_code == 'PNG' else 'tif'
        blend_name = bpy.path.display_name_from_filepath(bpy.data.filepath) or 'untitled'
        filename = f"{blend_name}_{_timestamp()}"
        filepath_no_ext = os.path.join(export_dir, filename)
        filepath = filepath_no_ext + f".{ext}"

        try:
            scene = context.scene
            if scene.camera:
                # 카메라가 있으면 정식 렌더 → Render Result 저장
                bpy.ops.render.render()
                img = bpy.data.images.get("Render Result")
                if not img or not img.has_data:
                    raise RuntimeError("렌더 결과가 없습니다.")
                img_settings = scene.render.image_settings
                prev_fmt = img_settings.file_format
                try:
                    img_settings.file_format = fmt_code
                    img.save_render(filepath=filepath, scene=scene)
                finally:
                    img_settings.file_format = prev_fmt
            else:
                # 카메라 없으면 뷰포트 기준 렌더로 폴백
                filepath = _viewport_render_to_file(context, fmt_code, filepath_no_ext)
        except Exception as e:
            self.report({'ERROR'}, f"렌더 저장 실패: {e}")
            return {'CANCELLED'}

        ok = launch_csp(prefs.csp_path, filepath)
        if not ok:
            self.report({'ERROR'}, "CSP 실행에 실패했습니다. 경로를 확인하세요.")
            return {'CANCELLED'}

        self.report({'INFO'}, f"저장 및 실행: {filepath}")
        return {'FINISHED'}


class CLIPSTUDIO_QUICKEDIT_OT_start(Operator):
    bl_idname = "clipstudio.quickedit_start"
    bl_label = "Quick Edit 시작 (CSP)"
    bl_description = "활성 텍스처 이미지를 임시 파일로 저장(또는 원본 경로 사용) 후 Clip Studio Paint로 엽니다"
    bl_options = {'REGISTER'}

    def execute(self, context):
        prefs = get_prefs()
        if not prefs or not prefs.csp_path:
            self.report({'ERROR'}, "CSP 경로가 설정되지 않았습니다. Preferences에서 지정하세요.")
            return {'CANCELLED'}

        img = get_active_image(context)
        if not img:
            self.report({'ERROR'}, "활성 이미지가 없습니다. 이미지 에디터나 텍스처 페인트에서 이미지를 선택하세요.")
            return {'CANCELLED'}

        was_packed = bool(getattr(img, 'packed_file', None))
        orig_path = bpy.path.abspath(img.filepath_raw or img.filepath)
        work_path = None

        try:
            if _image_has_file(img) and not was_packed:
                # 원본 경로를 그대로 사용
                work_path = orig_path
            else:
                # 임시 quickedit 경로에 저장
                qdir = _ensure_quickedit_path(prefs)
                name = _sanitize_filename(img.name)
                # 확장자 추정
                ext = os.path.splitext(orig_path)[1].lower() if orig_path else ''
                if ext not in ('.png', '.tif', '.tiff', '.jpg', '.jpeg', '.bmp', '.psd'):
                    ext = '.png'
                work_path = os.path.join(qdir, f"{name}{ext}")

                # 이미지 저장 (일시적으로 포맷 조정 가능)
                prev_fp = img.filepath
                prev_format = getattr(img, 'file_format', None)
                try:
                    if ext in ('.png', '.tif', '.tiff') and prev_format is not None:
                        img.file_format = 'PNG' if ext == '.png' else 'TIFF'
                    img.save(filepath=work_path)
                    # 이 세션에서는 해당 경로로 reload
                    img.filepath = work_path
                finally:
                    if prev_format is not None:
                        img.file_format = prev_format
                    # filepath는 세션 동안 work_path로 유지

            _set_session(img, {
                'orig_path': orig_path,
                'was_packed': was_packed,
                'work_path': work_path,
                'started': _timestamp(),
            })

            ok = launch_csp(prefs.csp_path, work_path)
            if not ok:
                raise RuntimeError("CSP 실행 실패")
        except Exception as e:
            self.report({'ERROR'}, f"Quick Edit 시작 실패: {e}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Quick Edit 대상: {img.name}")
        return {'FINISHED'}


class CLIPSTUDIO_QUICKEDIT_OT_reload(Operator):
    bl_idname = "clipstudio.quickedit_reload"
    bl_label = "Quick Edit 재불러오기"
    bl_description = "외부에서 저장된 변경 사항을 이미지에 반영합니다"

    def execute(self, context):
        img = get_active_image(context)
        if not img:
            self.report({'ERROR'}, "활성 이미지가 없습니다.")
            return {'CANCELLED'}
        try:
            img.reload()
        except Exception as e:
            self.report({'ERROR'}, f"재불러오기 실패: {e}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"재불러오기 완료: {img.name}")
        return {'FINISHED'}


class CLIPSTUDIO_QUICKEDIT_OT_finish(Operator):
    bl_idname = "clipstudio.quickedit_finish"
    bl_label = "Quick Edit 종료"
    bl_description = "필요 시 원본 경로에 덮어쓰고(복원) 임시 경로를 정리합니다"
    bl_options = {'REGISTER'}

    restore_original: BoolProperty(
        name="원본 경로 복원",
        description="세션 시작 시 원본 파일 경로가 있었다면 수정본을 원본에 덮어쓰고 경로를 되돌립니다",
        default=True,
    )

    repack_if_needed: BoolProperty(
        name="다시 패킹",
        description="시작 시 이미지가 패킹되어 있었다면 종료 시 다시 패킹합니다",
        default=False,
    )

    cleanup_temp: BoolProperty(
        name="임시파일 삭제",
        description="Quick Edit를 위해 생성된 임시 파일을 삭제합니다 (복원 후)",
        default=False,
    )

    def execute(self, context):
        img = get_active_image(context)
        if not img:
            self.report({'ERROR'}, "활성 이미지가 없습니다.")
            return {'CANCELLED'}

        sess = _session_for(img)
        if not sess:
            self.report({'WARNING'}, "활성 세션 정보가 없어 경로 복원 없이 종료합니다.")
            return {'FINISHED'}

        work_path = sess.get('work_path')
        orig_path = sess.get('orig_path')
        was_packed = sess.get('was_packed')

        try:
            if self.restore_original and orig_path and os.path.isfile(work_path):
                # 수정본을 원본에 덮어쓰기
                _ensure_dir(os.path.dirname(orig_path))
                shutil.copy2(work_path, orig_path)
                img.filepath = orig_path
                img.reload()

            if self.repack_if_needed and was_packed:
                try:
                    img.pack()
                except Exception:
                    pass

            if self.cleanup_temp and work_path and work_path != orig_path:
                try:
                    os.remove(work_path)
                except Exception:
                    pass
        finally:
            _del_session(img)

        self.report({'INFO'}, "Quick Edit 종료")
        return {'FINISHED'}


class VIEW3D_PT_clipstudio(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "ClipStudio"
    bl_label = "Clip Studio"

    def draw(self, context):
        layout = self.layout
        prefs = get_prefs()

        box = layout.box()
        row = box.row()
        row.label(text="상태", icon='INFO')
        box.label(text=f"CSP 경로: {prefs.csp_path if prefs and prefs.csp_path else '(미설정)'}")
        if prefs:
            box.prop(prefs, "auto_export")
            box.prop(prefs, "export_format")
            box.prop(prefs, "export_dir")
            box.operator("clipstudio.detect_path", icon='VIEWZOOM')

        layout.separator()
        col = layout.column()
        col.operator("clipstudio.hello", icon='CHECKMARK')
        col.operator("clipstudio.export_render_open", icon='RENDER_STILL')
        col.operator("clipstudio.open_file", icon='FILE_FOLDER')


class VIEW3D_PT_csp_quickedit(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "CSP QuickEdit"
    bl_label = "CSP Quick Edit"

    def draw(self, context):
        layout = self.layout
        prefs = get_prefs()
        img = get_active_image(context)

        box = layout.box()
        row = box.row()
        row.label(text="Clip Studio Paint", icon='BRUSH_DATA')
        box.prop(prefs, "csp_path")
        box.operator("clipstudio.detect_path", icon='VIEWZOOM')

        layout.separator()
        col = layout.column()
        col.label(text=f"활성 이미지: {img.name if img else '(없음)'}")
        if img:
            path = bpy.path.abspath(img.filepath_raw or img.filepath)
            col.label(text=f"경로: {path if path else '(임시/메모리)'}")
        col.separator()
        col.operator("clipstudio.quickedit_start", icon='EXTERNAL_DATA')
        col.operator("clipstudio.quickedit_reload", icon='FILE_REFRESH')
        col.operator("clipstudio.quickedit_finish", icon='CHECKMARK')


classes = (
    CLIPSTUDIO_Preferences,
    CLIPSTUDIO_OT_hello,
    CLIPSTUDIO_OT_detect_path,
    CLIPSTUDIO_OT_open_file,
    CLIPSTUDIO_OT_export_render_open,
    CLIPSTUDIO_QUICKEDIT_OT_start,
    CLIPSTUDIO_QUICKEDIT_OT_reload,
    CLIPSTUDIO_QUICKEDIT_OT_finish,
    VIEW3D_PT_csp_quickedit,
    VIEW3D_PT_clipstudio,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    print("[ClipStudio] Registered")


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    print("[ClipStudio] Unregistered")
