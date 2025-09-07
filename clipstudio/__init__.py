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
import math
import os
import sys
import subprocess
import shutil
from datetime import datetime
from mathutils import Matrix

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

# 캡쳐/투영 기본값 (요청사항: 1:1, 2048x2048, 임시카메라 기준)
CAPTURE_RES_X = 2048
CAPTURE_RES_Y = 2048
CAPTURE_PIXEL_ASPECT_X = 1.0
CAPTURE_PIXEL_ASPECT_Y = 1.0


# --------------------
# Debug helpers
# --------------------

def _safe_get(obj, attr, default=None):
    try:
        return getattr(obj, attr, default)
    except Exception:
        return default


def _print_camera_debug(tag: str, cam: bpy.types.Object | None, scene: bpy.types.Scene | None, extra: dict | None = None):
    try:
        if not cam or not cam.data:
            print(f"[ClipStudio][Debug][{tag}] Camera: None")
            return
        cd = cam.data
        ang = _safe_get(cd, 'angle', None)
        ang_x = _safe_get(cd, 'angle_x', None)
        ang_y = _safe_get(cd, 'angle_y', None)
        print(
            f"[ClipStudio][Debug][{tag}] cam='{cam.name}', lens={_safe_get(cd,'lens',None)}, sensor_fit={_safe_get(cd,'sensor_fit',None)}, "
            f"sensor=({_safe_get(cd,'sensor_width',None)}x{_safe_get(cd,'sensor_height',None)}), shift=({_safe_get(cd,'shift_x',None)},{_safe_get(cd,'shift_y',None)}), "
            f"clip=({_safe_get(cd,'clip_start',None)}->{_safe_get(cd,'clip_end',None)}), angle={ang}, angle_x={ang_x}, angle_y={ang_y}"
        )
        try:
            if ang_x and ang_y:
                ax = math.tan(ang_x * 0.5)
                ay = math.tan(ang_y * 0.5)
                calc_aspect = ax / ay if ay != 0 else None
                print(f"[ClipStudio][Debug][{tag}] fov_aspect_from_angles={calc_aspect}")
        except Exception:
            pass
        if scene:
            r = scene.render
            print(
                f"[ClipStudio][Debug][{tag}] render_res=({r.resolution_x}x{r.resolution_y})@{r.resolution_percentage}%, pixel_aspect=({r.pixel_aspect_x},{r.pixel_aspect_y}), "
                f"use_border={_safe_get(r,'use_border',False)}, border=({_safe_get(r,'border_min_x',0)},{_safe_get(r,'border_min_y',0)})-({_safe_get(r,'border_max_x',1)},{_safe_get(r,'border_max_y',1)})"
            )
        if extra:
            try:
                print(f"[ClipStudio][Debug][{tag}] extra={extra}")
            except Exception:
                pass
        try:
            mw = cam.matrix_world
            flat = [round(mw[i][j], 6) for i in range(4) for j in range(4)]
            print(f"[ClipStudio][Debug][{tag}] cam_mw={flat}")
        except Exception:
            pass
        try:
            vf = cd.view_frame(scene=scene)
            # view_frame returns 4 corners; print their lengths for quick sanity
            lens = [round(v.length, 6) for v in vf]
            print(f"[ClipStudio][Debug][{tag}] view_frame_lengths={lens}")
        except Exception:
            pass
    except Exception:
        pass


def _print_view_debug(tag: str, vctx: dict | None):
    try:
        if not vctx:
            print(f"[ClipStudio][Debug][{tag}] vctx=None")
            return
        reg = vctx.get('region')
        sp = vctx.get('space_data')
        r3d = vctx.get('region_3d')
        print(
            f"[ClipStudio][Debug][{tag}] region=({_safe_get(reg,'width',None)}x{_safe_get(reg,'height',None)}), "
            f"view_persp={_safe_get(r3d,'view_perspective',None)}, cam_zoom={_safe_get(r3d,'view_camera_zoom',None)}, cam_offset={_safe_get(r3d,'view_camera_offset',None)}, lens={_safe_get(sp,'lens',None)}"
        )
    except Exception:
        pass


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


def _matrix_to_list(mat: Matrix) -> list:
    try:
        return [mat[i][j] for i in range(4) for j in range(4)]
    except Exception:
        return []


def _list_to_matrix(vals: list) -> Matrix | None:
    try:
        if not vals or len(vals) != 16:
            return None
        rows = [vals[0:4], vals[4:8], vals[8:12], vals[12:16]]
        return Matrix(rows)
    except Exception:
        return None


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


def _camera_view_capture_to_file(context, vctx: dict, cam: bpy.types.Object, fmt_code: str, filepath_no_ext: str) -> str:
    scene = context.scene
    img_settings = scene.render.image_settings
    prev_fmt = img_settings.file_format
    prev_path = scene.render.filepath
    prev_resx = scene.render.resolution_x
    prev_resy = scene.render.resolution_y
    prev_resperc = scene.render.resolution_percentage
    prev_pix_aspx = scene.render.pixel_aspect_x
    prev_pix_aspy = scene.render.pixel_aspect_y
    prev_cam = scene.camera
    
    # Prepare shading overrides for flat/unlit capture
    space = vctx.get('space_data') if vctx else None
    prev_space_shading = {}
    prev_overlay = {}
    scene_display = getattr(scene, 'display', None)
    scene_shading = getattr(scene_display, 'shading', None) if scene_display else None
    prev_scene_shading = {}

    try:
        # Match render settings to viewport region
        img_settings.file_format = fmt_code
        scene.render.filepath = filepath_no_ext
        # 요청사항: 고정 1:1 정사각 해상도로 캡쳐
        scene.render.resolution_x = CAPTURE_RES_X
        scene.render.resolution_y = CAPTURE_RES_Y
        scene.render.resolution_percentage = 100
        scene.render.pixel_aspect_x = CAPTURE_PIXEL_ASPECT_X
        scene.render.pixel_aspect_y = CAPTURE_PIXEL_ASPECT_Y
        # Use the provided camera
        scene.camera = cam
        # Force Workbench Solid + Flat lighting with textures, overlays off
        try:
            if space and hasattr(space, 'shading'):
                sh = space.shading
                prev_space_shading = {
                    'type': getattr(sh, 'type', None),
                    'light': getattr(sh, 'light', None),
                    'color_type': getattr(sh, 'color_type', None),
                    'use_scene_lights': getattr(sh, 'use_scene_lights', None),
                    'use_scene_world': getattr(sh, 'use_scene_world', None),
                    'show_shadows': getattr(sh, 'show_shadows', None),
                    'show_cavity': getattr(sh, 'show_cavity', None),
                    'show_object_outline': getattr(sh, 'show_object_outline', None),
                }
                if hasattr(sh, 'type'):
                    sh.type = 'SOLID'
                if hasattr(sh, 'light'):
                    sh.light = 'FLAT'
                if hasattr(sh, 'color_type'):
                    sh.color_type = 'TEXTURE'
                if hasattr(sh, 'use_scene_lights'):
                    sh.use_scene_lights = False
                if hasattr(sh, 'use_scene_world'):
                    sh.use_scene_world = False
                if hasattr(sh, 'show_shadows'):
                    sh.show_shadows = False
                if hasattr(sh, 'show_cavity'):
                    sh.show_cavity = False
                if hasattr(sh, 'show_object_outline'):
                    sh.show_object_outline = False
            if space and hasattr(space, 'overlay') and space.overlay:
                ov = space.overlay
                prev_overlay = {'show_overlays': getattr(ov, 'show_overlays', None)}
                if hasattr(ov, 'show_overlays'):
                    ov.show_overlays = False
        except Exception:
            pass
        # Also set scene display shading for non-view-context OpenGL render path
        try:
            if scene_shading:
                prev_scene_shading = {
                    'light': getattr(scene_shading, 'light', None),
                    'color_type': getattr(scene_shading, 'color_type', None),
                    'use_scene_lights': getattr(scene_shading, 'use_scene_lights', None),
                    'use_scene_world': getattr(scene_shading, 'use_scene_world', None),
                    'show_shadows': getattr(scene_shading, 'show_shadows', None),
                    'show_cavity': getattr(scene_shading, 'show_cavity', None),
                    'show_object_outline': getattr(scene_shading, 'show_object_outline', None),
                }
                if hasattr(scene_shading, 'light'):
                    scene_shading.light = 'FLAT'
                if hasattr(scene_shading, 'color_type'):
                    scene_shading.color_type = 'TEXTURE'
                if hasattr(scene_shading, 'use_scene_lights'):
                    scene_shading.use_scene_lights = False
                if hasattr(scene_shading, 'use_scene_world'):
                    scene_shading.use_scene_world = False
                if hasattr(scene_shading, 'show_shadows'):
                    scene_shading.show_shadows = False
                if hasattr(scene_shading, 'show_cavity'):
                    scene_shading.show_cavity = False
                if hasattr(scene_shading, 'show_object_outline'):
                    scene_shading.show_object_outline = False
        except Exception:
            pass
        # Debug
        _print_camera_debug("Capture", cam, scene, {
            'fmt': fmt_code,
            'filepath_no_ext': filepath_no_ext,
            'res': f"{scene.render.resolution_x}x{scene.render.resolution_y}",
            'px_aspect': f"{scene.render.pixel_aspect_x},{scene.render.pixel_aspect_y}",
        })
        # OpenGL render from camera
        bpy.ops.render.opengl(view_context=False, write_still=True)
    finally:
        # Restore settings
        scene.render.filepath = prev_path
        scene.render.resolution_x = prev_resx
        scene.render.resolution_y = prev_resy
        scene.render.resolution_percentage = prev_resperc
        scene.render.pixel_aspect_x = prev_pix_aspx
        scene.render.pixel_aspect_y = prev_pix_aspy
        img_settings.file_format = prev_fmt
        scene.camera = prev_cam
        # Restore viewport shading/overlays
        try:
            if space and hasattr(space, 'shading') and prev_space_shading:
                sh = space.shading
                if 'type' in prev_space_shading and prev_space_shading['type'] is not None and hasattr(sh, 'type'):
                    sh.type = prev_space_shading['type']
                if 'light' in prev_space_shading and prev_space_shading['light'] is not None and hasattr(sh, 'light'):
                    sh.light = prev_space_shading['light']
                if 'color_type' in prev_space_shading and prev_space_shading['color_type'] is not None and hasattr(sh, 'color_type'):
                    sh.color_type = prev_space_shading['color_type']
                if 'use_scene_lights' in prev_space_shading and prev_space_shading['use_scene_lights'] is not None and hasattr(sh, 'use_scene_lights'):
                    sh.use_scene_lights = prev_space_shading['use_scene_lights']
                if 'use_scene_world' in prev_space_shading and prev_space_shading['use_scene_world'] is not None and hasattr(sh, 'use_scene_world'):
                    sh.use_scene_world = prev_space_shading['use_scene_world']
                if 'show_shadows' in prev_space_shading and prev_space_shading['show_shadows'] is not None and hasattr(sh, 'show_shadows'):
                    sh.show_shadows = prev_space_shading['show_shadows']
                if 'show_cavity' in prev_space_shading and prev_space_shading['show_cavity'] is not None and hasattr(sh, 'show_cavity'):
                    sh.show_cavity = prev_space_shading['show_cavity']
                if 'show_object_outline' in prev_space_shading and prev_space_shading['show_object_outline'] is not None and hasattr(sh, 'show_object_outline'):
                    sh.show_object_outline = prev_space_shading['show_object_outline']
            if space and hasattr(space, 'overlay') and prev_overlay:
                ov = space.overlay
                if 'show_overlays' in prev_overlay and prev_overlay['show_overlays'] is not None and hasattr(ov, 'show_overlays'):
                    ov.show_overlays = prev_overlay['show_overlays']
        except Exception:
            pass
        # Restore scene display shading
        try:
            if scene_shading and prev_scene_shading:
                if 'light' in prev_scene_shading and prev_scene_shading['light'] is not None and hasattr(scene_shading, 'light'):
                    scene_shading.light = prev_scene_shading['light']
                if 'color_type' in prev_scene_shading and prev_scene_shading['color_type'] is not None and hasattr(scene_shading, 'color_type'):
                    scene_shading.color_type = prev_scene_shading['color_type']
                if 'use_scene_lights' in prev_scene_shading and prev_scene_shading['use_scene_lights'] is not None and hasattr(scene_shading, 'use_scene_lights'):
                    scene_shading.use_scene_lights = prev_scene_shading['use_scene_lights']
                if 'use_scene_world' in prev_scene_shading and prev_scene_shading['use_scene_world'] is not None and hasattr(scene_shading, 'use_scene_world'):
                    scene_shading.use_scene_world = prev_scene_shading['use_scene_world']
                if 'show_shadows' in prev_scene_shading and prev_scene_shading['show_shadows'] is not None and hasattr(scene_shading, 'show_shadows'):
                    scene_shading.show_shadows = prev_scene_shading['show_shadows']
                if 'show_cavity' in prev_scene_shading and prev_scene_shading['show_cavity'] is not None and hasattr(scene_shading, 'show_cavity'):
                    scene_shading.show_cavity = prev_scene_shading['show_cavity']
                if 'show_object_outline' in prev_scene_shading and prev_scene_shading['show_object_outline'] is not None and hasattr(scene_shading, 'show_object_outline'):
                    scene_shading.show_object_outline = prev_scene_shading['show_object_outline']
        except Exception:
            pass

    # Guess saved path
    ext = 'png' if fmt_code == 'PNG' else ('tif' if fmt_code == 'TIFF' else fmt_code.lower())
    cand1 = filepath_no_ext + "." + ext
    cand2 = filepath_no_ext + ".tiff"
    return cand1 if os.path.isfile(cand1) else (cand2 if os.path.isfile(cand2) else cand1)

def _create_tmp_camera_from_view(vctx, name: str = None):
    scene = bpy.context.scene
    cam_name = name or "CSP_QE_TMP_CAM"
    cam_data = bpy.data.cameras.new(cam_name)
    cam = bpy.data.objects.new(cam_name, cam_data)
    scene.collection.objects.link(cam)
    vl = bpy.context.view_layer
    prev_active = vl.objects.active
    prev_scene_cam = scene.camera if scene else None
    try:
        vl.objects.active = cam
        # Align camera to current viewport precisely via operator
        r3d = vctx.get('region_3d') if vctx else None
        space = vctx.get('space_data') if vctx else None
        # Pre-configure lens/sensor to match the viewport
        cam.data.type = 'PERSP'
        try:
            if space and hasattr(space, 'lens'):
                cam.data.lens = space.lens
        except Exception:
            pass
        # 요청사항: 정사각형(1:1) 센서로 고정 + 세로기준(VERTICAL)로 맞춤
        try:
            cam.data.sensor_fit = 'VERTICAL'
            cam.data.sensor_width = 36.0
            cam.data.sensor_height = 36.0
        except Exception:
            pass
        # Set as scene camera before aligning
        try:
            scene.camera = cam
        except Exception:
            pass
        try:
            with bpy.context.temp_override(**_override_from_view3d(vctx)):
                bpy.ops.view3d.camera_to_view()
        except Exception as e:
            print(f"[ClipStudio] camera_to_view failed: {e}")
        vp = getattr(r3d, 'view_perspective', None) if r3d else None
        try:
            region = vctx.get('region') if vctx else None
            print(f"[ClipStudio] Created temp camera {cam.name}, view_persp={vp}, lens={getattr(space,'lens',None)}, sensor=({cam.data.sensor_width},{cam.data.sensor_height}), capture=({CAPTURE_RES_X}x{CAPTURE_RES_Y}), region=({getattr(region,'width',None)}x{getattr(region,'height',None)})")
        except Exception:
            pass
    finally:
        if prev_active:
            vl.objects.active = prev_active
        # Restore previous scene camera to avoid sticking camera after Start
        try:
            if prev_scene_cam is not None:
                scene.camera = prev_scene_cam
        except Exception:
            pass
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

    cleanup_choice: EnumProperty(
    	name="Existing CSP_QE cameras",
    	items=[
    		('DELETE', "Delete", "Delete found cameras"),
    		('KEEP', "Keep", "Keep found cameras"),
    		('CANCEL', "Cancel", "Cancel Start")
    	],
    	default='DELETE',
    )

    found_names: StringProperty(name="Found", default="", options={'HIDDEN'})

    def invoke(self, context, event):
        names = [obj.name for obj in bpy.data.objects if obj.type == 'CAMERA' and obj.name.startswith('CSP_QE_')]
        if names:
            self.found_names = "\n".join(sorted(names))
            return context.window_manager.invoke_props_dialog(self, width=420)
        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        if self.found_names:
            layout.label(text="Found existing CSP_QE cameras:")
            for nm in self.found_names.split("\n"):
                layout.label(text=f"- {nm}")
            layout.separator()
            layout.prop(self, "cleanup_choice", expand=True)

    def execute(self, context):
        # Handle cleanup choice
        if self.found_names:
            names = [n for n in self.found_names.split("\n") if n.strip()]
            if self.cleanup_choice == 'CANCEL':
                self.report({'INFO'}, "Start cancelled by user")
                return {'CANCELLED'}
            elif self.cleanup_choice == 'DELETE':
                for nm in names:
                    cam = bpy.data.objects.get(nm)
                    if cam:
                        try:
                            # Unlink from all scenes
                            for scn in bpy.data.scenes:
                                try:
                                    scn.collection.objects.unlink(cam)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        try:
                            bpy.data.objects.remove(cam, do_unlink=True)
                        except Exception:
                            pass
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
        _print_view_debug("Start:Before", vctx)

        # Create a temp camera from current view (used for both capture and apply)
        cam = None
        prev_cam_name = bpy.context.scene.camera.name if (bpy.context.scene and bpy.context.scene.camera) else ""
        qdir = _ensure_quickedit_path(prefs)
        name = _sanitize_filename(dest_img.name)
        basename = f"{name}_view_{_timestamp()}"
        filepath_no_ext = os.path.join(qdir, basename)
        try:
            # Create camera first to lock exact FOV/aspect
            cam = _create_tmp_camera_from_view(vctx, name=f"CSP_QE_CAM_{_timestamp()}")
            # Capture from saved camera using OpenGL (camera mode)
            proj_path = _camera_view_capture_to_file(context, vctx, cam, 'PNG', filepath_no_ext)
        except Exception as e:
            self.report({'ERROR'}, f"Viewport capture failed: {e}")
            return {'CANCELLED'}

        # 캡처 이미지를 블렌더에 로드
        try:
            proj_img = bpy.data.images.load(proj_path, check_existing=True)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load capture image: {e}")
            return {'CANCELLED'}

        # Get capture/image and viewport sizes
        cap_w = getattr(proj_img, 'size', [0, 0])[0] if hasattr(proj_img, 'size') else 0
        cap_h = getattr(proj_img, 'size', [0, 0])[1] if hasattr(proj_img, 'size') else 0
        region = vctx.get('region') if vctx else None
        reg_w = getattr(region, 'width', 0) if region else 0
        reg_h = getattr(region, 'height', 0) if region else 0
        # Camera props snapshot
        cam_data = cam.data if cam else None
        cam_lens = getattr(cam_data, 'lens', 0.0) if cam_data else 0.0
        # 센서핏은 세션 저장도 'VERTICAL'로 고정
        cam_sensor_fit = 'VERTICAL'
        cam_sensor_width = getattr(cam_data, 'sensor_width', 36.0) if cam_data else 36.0
        cam_sensor_height = getattr(cam_data, 'sensor_height', 24.0) if cam_data else 24.0
        cam_shift_x = getattr(cam_data, 'shift_x', 0.0) if cam_data else 0.0
        cam_shift_y = getattr(cam_data, 'shift_y', 0.0) if cam_data else 0.0
        cam_mw = _matrix_to_list(cam.matrix_world) if cam else []

        # Debug dump
        _print_camera_debug("Start:AfterCapture", cam, context.scene, {
            'proj_path': proj_path,
            'cap_size': f"{cap_w}x{cap_h}",
            'region_size': f"{reg_w}x{reg_h}",
        })

        # Save session (keyed by target image)
        _set_session(dest_img, {
            'dest_image_name': dest_img.name,
            'proj_path': proj_path,
            'proj_image_name': proj_img.name,
            'started': _timestamp(),
            'cam_name': cam.name if cam else "",
            'prev_cam_name': prev_cam_name,
            'cap_w': cap_w,
            'cap_h': cap_h,
            'reg_w': reg_w,
            'reg_h': reg_h,
            'cam_lens': cam_lens,
            'cam_sensor_fit': cam_sensor_fit,
            'cam_sensor_width': cam_sensor_width,
            'cam_sensor_height': cam_sensor_height,
            'cam_shift_x': cam_shift_x,
            'cam_shift_y': cam_shift_y,
            'cam_mw': cam_mw,
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
        _print_view_debug("Apply:Before", vctx)

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
                # Use saved camera from Start
                cam_name = sess.get('cam_name')
                cam = bpy.data.objects.get(cam_name) if cam_name else None
                if cam is None:
                    raise RuntimeError("Saved camera not found. Run Start again.")
                # Enforce saved camera transform and optics snapshot from Start
                try:
                    sv = sess
                    mw = _list_to_matrix(sv.get('cam_mw')) if sv else None
                    if mw is not None:
                        cam.matrix_world = mw
                    camd = cam.data
                    camd.type = 'PERSP'
                    # 요청사항: 세로 기준 고정
                    camd.sensor_fit = 'VERTICAL'
                    if sv:
                        if 'cam_lens' in sv:
                            camd.lens = float(sv['cam_lens'])
                        if 'cam_sensor_width' in sv:
                            camd.sensor_width = float(sv['cam_sensor_width'])
                        if 'cam_sensor_height' in sv:
                            camd.sensor_height = float(sv['cam_sensor_height'])
                        if 'cam_shift_x' in sv:
                            camd.shift_x = float(sv['cam_shift_x'])
                        if 'cam_shift_y' in sv:
                            camd.shift_y = float(sv['cam_shift_y'])
                except Exception:
                    pass
                try:
                    scene.camera = cam
                except Exception:
                    pass

                # Debug: Camera & session info
                try:
                    _print_camera_debug("Apply:CameraSetup", cam, scene, {
                        'sess_reg': f"{sess.get('reg_w')}x{sess.get('reg_h')}",
                        'sess_cap': f"{sess.get('cap_w')}x{sess.get('cap_h')}",
                        'src_img': f"{getattr(src_img,'size',[0,0])[0]}x{getattr(src_img,'size',[0,0])[1]}",
                        'dst_img': f"{getattr(dest_img,'size',[0,0])[0]}x{getattr(dest_img,'size',[0,0])[1]}",
                    })
                except Exception:
                    pass

                # Prepare temporary UV for camera projection via UV Project modifier
                tmp_uv_name = "CSP_QE_TMP_UV"
                uv_mod = None
                try:
                    me = target_ob.data
                    if hasattr(me, 'uv_layers'):
                        # Preserve original active UV for baking target
                        orig_active_index = me.uv_layers.active_index if me.uv_layers.active else 0
                        if me.uv_layers.get(tmp_uv_name) is None:
                            me.uv_layers.new(name=tmp_uv_name)
                            # Restore original active UV
                            try:
                                me.uv_layers.active_index = orig_active_index
                            except Exception:
                                pass
                        # Add UV Project modifier
                        uv_mod = target_ob.modifiers.new(name="CSP_QE_UVPROJECT", type='UV_PROJECT')
                        try:
                            uv_mod.uv_layer = tmp_uv_name
                        except Exception:
                            pass
                        # Set projector camera
                        try:
                            uv_mod.projectors[0].object = cam
                        except Exception:
                            try:
                                uv_mod.projectors[0] = cam
                            except Exception:
                                pass
                        # 투영 스케일: 1.0로 설정 (0.5는 절반 크기로 축소되는 문제가 있음)
                        try:
                            uv_mod.scale_x = 1.0
                            uv_mod.scale_y = 1.0
                        except Exception:
                            pass
                        try:
                            print(f"[ClipStudio][Debug][Apply:UVProject] initial aspect=({uv_mod.aspect_x},{uv_mod.aspect_y}), scale=({uv_mod.scale_x},{uv_mod.scale_y})")
                        except Exception:
                            pass
                        # 요청사항: 캡쳐 해상도(정사각) 기준으로 UV Project 종횡비 설정
                        try:
                            cap_w = int(sess.get('cap_w') or CAPTURE_RES_X)
                            cap_h = int(sess.get('cap_h') or CAPTURE_RES_Y)
                            if cap_w <= 0: cap_w = CAPTURE_RES_X
                            if cap_h <= 0: cap_h = CAPTURE_RES_Y
                            uv_mod.aspect_x = float(cap_w)
                            uv_mod.aspect_y = float(cap_h)
                        except Exception:
                            pass
                        try:
                            print(f"[ClipStudio][Debug][Apply:UVProject] set aspect=({uv_mod.aspect_x},{uv_mod.aspect_y}), scale=({uv_mod.scale_x},{uv_mod.scale_y})")
                        except Exception:
                            pass
                except Exception:
                    pass

                # Temporary material (UV -> source image -> Emission)
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
                uvmap = nt.nodes.new('ShaderNodeUVMap')
                try:
                    uvmap.uv_map = tmp_uv_name
                except Exception:
                    pass
                nt.links.new(uvmap.outputs['UV'], img_src.inputs['Vector'])
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

                # 요청사항: 베이크 중에도 캡쳐 해상도(정사각)로 고정
                prev_resx = scene.render.resolution_x
                prev_resy = scene.render.resolution_y
                prev_resperc = scene.render.resolution_percentage
                prev_pix_aspx = scene.render.pixel_aspect_x
                prev_pix_aspy = scene.render.pixel_aspect_y
                try:
                    cap_w = int(sess.get('cap_w') or CAPTURE_RES_X)
                    cap_h = int(sess.get('cap_h') or CAPTURE_RES_Y)
                    if cap_w > 0 and cap_h > 0:
                        scene.render.resolution_x = cap_w
                        scene.render.resolution_y = cap_h
                    scene.render.resolution_percentage = 100
                    scene.render.pixel_aspect_x = CAPTURE_PIXEL_ASPECT_X
                    scene.render.pixel_aspect_y = CAPTURE_PIXEL_ASPECT_Y
                except Exception:
                    pass

                # Switch to Cycles and bake (EMIT)
                scene.render.engine = 'CYCLES'
                # 선택 상태 정리
                for ob in bpy.context.view_layer.objects:
                    ob.select_set(False)
                target_ob.select_set(True)
                _set_active(target_ob)
                print(f"[ClipStudio][Debug][Apply:Bake] res=({scene.render.resolution_x}x{scene.render.resolution_y}), pixel_aspect=({scene.render.pixel_aspect_x},{scene.render.pixel_aspect_y}), engine={scene.render.engine}")
                bpy.ops.object.bake(type='EMIT', margin=2, use_clear=False)

                # 베이크 결과는 이미지 데이터에 즉시 반영됨. reload는 메모리 변경을 덮어쓸 수 있으므로 호출하지 않음.

                # Restore materials
                target_ob.data.materials.clear()
                for m in original_mats:
                    if m:
                        target_ob.data.materials.append(m)

                # Remove temp UV modifier and UV map
                try:
                    if uv_mod:
                        target_ob.modifiers.remove(uv_mod)
                except Exception:
                    pass
                try:
                    me = target_ob.data
                    uv = me.uv_layers.get(tmp_uv_name) if hasattr(me, 'uv_layers') else None
                    if uv:
                        me.uv_layers.remove(uv)
                except Exception:
                    pass
                # Restore render resolution settings
                try:
                    scene.render.resolution_x = prev_resx
                    scene.render.resolution_y = prev_resy
                    scene.render.resolution_percentage = prev_resperc
                    scene.render.pixel_aspect_x = prev_pix_aspx
                    scene.render.pixel_aspect_y = prev_pix_aspy
                except Exception:
                    pass

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
