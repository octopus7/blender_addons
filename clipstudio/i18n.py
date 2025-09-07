import sys
import os
import locale

# Supported languages list (extendable)
SUPPORTED_LANGS = [
    {"key": "EN", "code": "en"},
    {"key": "KO", "code": "ko"},
    {"key": "JA", "code": "ja"},
]


def code_from_key(key: str) -> str:
    key = (key or '').upper()
    for it in SUPPORTED_LANGS:
        if it["key"] == key:
            return it["code"]
    return "en"


def key_from_code(code: str) -> str:
    code = (code or '').lower()
    for it in SUPPORTED_LANGS:
        if it["code"] == code:
            return it["key"]
    return "EN"


# UI strings dictionary
I18N = {
    'UI Language': {
        'en': 'UI Language',
        'ko': 'UI 언어',
        'ja': 'UI言語',
    },
    'Auto (OS)': {
        'en': 'Auto (OS)',
        'ko': '자동 (OS 기준)',
        'ja': '自動 (OS)',
    },
    'English': {
        'en': 'English',
        'ko': '영어',
        'ja': '英語',
    },
    'Korean': {
        'en': 'Korean',
        'ko': '한국어',
        'ja': '韓国語',
    },
    'Japanese': {
        'en': 'Japanese',
        'ko': '일본어',
        'ja': '日本語',
    },
    'Status': {
        'en': 'Status',
        'ko': '상태',
        'ja': 'ステータス',
    },
    'Clip Studio Path': {
        'en': 'Clip Studio Path',
        'ko': '클립 스튜디오 경로',
        'ja': 'CLIP STUDIO パス',
    },
    'Show Path Controls in Viewport': {
        'en': 'Show Path Controls in Viewport',
        'ko': '뷰포트에서 경로 설정 표시',
        'ja': 'ビューポートでパス設定を表示',
    },
    'Detect Path': {
        'en': 'Detect Path',
        'ko': '경로 자동 감지',
        'ja': 'パスを検出',
    },
    'Available': {
        'en': 'Available',
        'ko': '확인됨',
        'ja': '利用可能',
    },
    'Path not set / Executable missing': {
        'en': 'Path not set / Executable missing',
        'ko': '경로 미지정 / 실행 파일 없음',
        'ja': 'パス未設定 / 実行ファイルなし',
    },
    'Active Image': {
        'en': 'Active Image',
        'ko': '활성 이미지',
        'ja': 'アクティブ画像',
    },
    'Path': {
        'en': 'Path',
        'ko': '경로',
        'ja': 'パス',
    },
    'Start Quick Edit (CSP)': {
        'en': 'Start Quick Edit (CSP)',
        'ko': '퀵 에딧 시작 (CSP)',
        'ja': 'クイック編集開始 (CSP)',
    },
    'Apply Projection (Active Obj)': {
        'en': 'Apply Projection (Active Obj)',
        'ko': '프로젝션 적용 (활성 오브젝트)',
        'ja': '投影を適用（アクティブ）',
    },
    'Clean Temporary Files': {
        'en': 'Clean Temporary Files',
        'ko': '임시 파일 정리',
        'ja': '一時ファイルを削除',
    },
    'Found existing CSP_QE cameras:': {
        'en': 'Found existing CSP_QE cameras:',
        'ko': '기존 CSP_QE 카메라를 찾았습니다:',
        'ja': '既存のCSP_QEカメラが見つかりました:',
    },
    'Existing CSP_QE cameras': {
        'en': 'Existing CSP_QE cameras',
        'ko': '기존 CSP_QE 카메라',
        'ja': '既存のCSP_QEカメラ',
    },
    'Delete': {
        'en': 'Delete',
        'ko': '삭제',
        'ja': '削除',
    },
    'Keep': {
        'en': 'Keep',
        'ko': '유지',
        'ja': '保持',
    },
    'Cancel': {
        'en': 'Cancel',
        'ko': '취소',
        'ja': 'キャンセル',
    },
    'Delete found cameras': {
        'en': 'Delete found cameras',
        'ko': '발견된 카메라 삭제',
        'ja': '見つかったカメラを削除',
    },
    'Keep found cameras': {
        'en': 'Keep found cameras',
        'ko': '발견된 카메라 유지',
        'ja': '見つかったカメラを保持',
    },
    'Cancel Start': {
        'en': 'Cancel Start',
        'ko': '시작 취소',
        'ja': '開始をキャンセル',
    },
    'Console logs are always English.': {
        'en': 'Console logs are always English.',
        'ko': '콘솔 로그는 항상 영어입니다.',
        'ja': 'コンソールログは常に英語です。',
    },
    'Detected OS language': {
        'en': 'Detected OS language',
        'ko': '감지된 OS 언어',
        'ja': '検出されたOS言語',
    },
    # Reports / UI messages
    'Add-on preferences not found.': {
        'en': 'Add-on preferences not found.',
        'ko': '애드온 환경설정을 찾을 수 없습니다.',
        'ja': 'アドオンの環境設定が見つかりません。',
    },
    'Path set: {path}': {
        'en': 'Path set: {path}',
        'ko': '경로가 설정되었습니다: {path}',
        'ja': 'パスを設定しました: {path}',
    },
    'Installation not found. Please set manually.': {
        'en': 'Installation not found. Please set manually.',
        'ko': '설치를 찾을 수 없습니다. 수동으로 설정하세요.',
        'ja': 'インストールが見つかりません。手動で設定してください。',
    },
    'Start cancelled by user': {
        'en': 'Start cancelled by user',
        'ko': '시작이 사용자에 의해 취소되었습니다',
        'ja': '開始がユーザーによりキャンセルされました',
    },
    'CSP path is not set. Set it in Preferences.': {
        'en': 'CSP path is not set. Set it in Preferences.',
        'ko': 'CSP 경로가 설정되지 않았습니다. 환경설정에서 설정하세요.',
        'ja': 'CSPのパスが未設定です。環境設定で設定してください。',
    },
    'No active texture image. Select one in Image Editor/Texture Paint/Active Image Texture node.': {
        'en': 'No active texture image. Select one in Image Editor/Texture Paint/Active Image Texture node.',
        'ko': '활성 텍스처 이미지가 없습니다. 이미지 에디터/텍스처 페인트/활성 이미지 텍스처 노드에서 선택하세요.',
        'ja': '有効なテクスチャ画像がありません。画像エディター/テクスチャペイント/アクティブな画像テクスチャノードで選択してください。',
    },
    '3D Viewport not found.': {
        'en': '3D Viewport not found.',
        'ko': '3D 뷰포트를 찾을 수 없습니다.',
        'ja': '3Dビューポートが見つかりません。',
    },
    'Viewport capture failed: {error}': {
        'en': 'Viewport capture failed: {error}',
        'ko': '뷰포트 캡처 실패: {error}',
        'ja': 'ビューポートのキャプチャに失敗しました: {error}',
    },
    'Failed to load capture image: {error}': {
        'en': 'Failed to load capture image: {error}',
        'ko': '캡처 이미지를 불러오지 못했습니다: {error}',
        'ja': 'キャプチャ画像の読み込みに失敗しました: {error}',
    },
    'Failed to launch CSP. Check the path.': {
        'en': 'Failed to launch CSP. Check the path.',
        'ko': 'CSP 실행에 실패했습니다. 경로를 확인하세요.',
        'ja': 'CSPの起動に失敗しました。パスを確認してください。',
    },
    'Quick Edit started: opened capture in CSP, created camera {name}': {
        'en': 'Quick Edit started: opened capture in CSP, created camera {name}',
        'ko': '퀵 에딧 시작: CSP에서 캡처를 열고 카메라 {name}을(를) 생성했습니다',
        'ja': 'クイック編集を開始: CSPでキャプチャを開き、カメラ{name}を作成しました',
    },
    'No active image.': {
        'en': 'No active image.',
        'ko': '활성 이미지가 없습니다.',
        'ja': 'アクティブな画像がありません。',
    },
    'No active session to clean.': {
        'en': 'No active session to clean.',
        'ko': '정리할 활성 세션이 없습니다.',
        'ja': 'クリーンアップするアクティブなセッションがありません。',
    },
    'Quick Edit session cleaned': {
        'en': 'Quick Edit session cleaned',
        'ko': '퀵 에딧 세션이 정리되었습니다',
        'ja': 'クイック編集セッションをクリーンアップしました',
    },
    'No active mesh object.': {
        'en': 'No active mesh object.',
        'ko': '활성 메쉬 오브젝트가 없습니다.',
        'ja': 'アクティブなメッシュオブジェクトがありません。',
    },
    'No Quick Edit session. Run Start first.': {
        'en': 'No Quick Edit session. Run Start first.',
        'ko': '퀵 에딧 세션이 없습니다. 먼저 Start를 실행하세요.',
        'ja': 'クイック編集セッションがありません。先にStartを実行してください。',
    },
    'Source capture not found. Edit/Save in CSP then retry.': {
        'en': 'Source capture not found. Edit/Save in CSP then retry.',
        'ko': '원본 캡처를 찾을 수 없습니다. CSP에서 편집/저장 후 다시 시도하세요.',
        'ja': '元のキャプチャが見つかりません。CSPで編集/保存してから再試行してください。',
    },
    'Failed to load source image: {error}': {
        'en': 'Failed to load source image: {error}',
        'ko': '소스 이미지를 불러오지 못했습니다: {error}',
        'ja': 'ソース画像の読み込みに失敗しました: {error}',
    },
    'Projection applied (Bake)': {
        'en': 'Projection applied (Bake)',
        'ko': '프로젝션 적용됨 (베이크)',
        'ja': '投影を適用 (ベイク)',
    },
    'Projection failed: {error}': {
        'en': 'Projection failed: {error}',
        'ko': '프로젝션 실패: {error}',
        'ja': '投影に失敗しました: {error}',
    },
    'Projection applied (Active Object)': {
        'en': 'Projection applied (Active Object)',
        'ko': '프로젝션 적용됨 (활성 오브젝트)',
        'ja': '投影を適用（アクティブオブジェクト）',
    },
}


def detect_os_lang_code() -> str:
    try:
        if sys.platform.startswith('win'):
            try:
                import ctypes
                langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
                msg = locale.windows_locale.get(int(langid), '') or ''
                msg = msg.lower()
            except Exception:
                msg = ''
        else:
            msg = ''
            for var in ('LC_ALL', 'LC_MESSAGES', 'LANG'):
                val = os.environ.get(var)
                if val:
                    msg = val
                    break
            msg = (msg or '').split('.')[0].split('@')[0].lower()
        if msg.startswith('ko'):
            return 'ko'
        if msg.startswith('ja'):
            return 'ja'
        if msg.startswith('en'):
            return 'en'
    except Exception:
        pass
    return 'en'


def lang_code_for_pref(pref_value: str) -> str:
    if (pref_value or '').upper() == 'AUTO':
        return detect_os_lang_code()
    return code_from_key(pref_value)


_lang_getter = None


def set_lang_getter(func):
    global _lang_getter
    _lang_getter = func


def current_lang_code() -> str:
    try:
        if _lang_getter:
            return _lang_getter() or 'en'
    except Exception:
        pass
    return detect_os_lang_code()


def t(key: str, lang_code: str | None = None) -> str:
    code = (lang_code or current_lang_code())
    try:
        return I18N.get(key, {}).get(code, I18N.get(key, {}).get('en', key))
    except Exception:
        return key


def tf(key: str, lang_code: str | None = None, **kwargs) -> str:
    s = t(key, lang_code=lang_code)
    try:
        return s.format(**kwargs)
    except Exception:
        return s


def language_name_for_code(code: str, in_lang_code: str | None = None) -> str:
    key = key_from_code(code)
    name_key = {
        'EN': 'English',
        'KO': 'Korean',
        'JA': 'Japanese',
    }.get(key, 'English')
    return t(name_key, lang_code=in_lang_code)


def enum_items(lang_code: str | None = None):
    code = lang_code or current_lang_code()
    items = [
        ('AUTO', t('Auto (OS)', lang_code=code), t('Auto (OS)', lang_code=code)),
    ]
    for it in SUPPORTED_LANGS:
        key = it['key']
        name_key = {
            'EN': 'English',
            'KO': 'Korean',
            'JA': 'Japanese',
        }.get(key, 'English')
        label = t(name_key, lang_code=code)
        items.append((key, label, label))
    return items
