# Clip Studio Bridge (Blender Add-on)

Blender의 3D Viewport를 캡처해 Clip Studio Paint(CSP)에서 빠르게 편집하고, 저장본을 다시 활성 오브젝트의 텍스처에 "카메라 기반 투영 + 베이크"로 반영하는 워크플로우를 제공합니다. Windows 우선 지원, Blender 4.5 LTS 이상을 대상으로 합니다.

**핵심 기능**
- 뷰포트 캡처 → CSP 자동 실행/열기 → 저장 → Blender로 즉시 투영(프로젝션)
- 캡처 해상도 고정: 1:1 정사각(기본 2048x2048), 색 관리 Standard/sRGB로 통일
- 프로젝션은 Cycles EMIT 베이크로 적용(임시 UV/머티리얼/모디파이어는 자동 정리)
- UI 언어: 자동(OS) + English/한국어/日本語 지원
- 뷰포트 패널에서 CSP 경로 표시/자동 감지(표시/숨김 토글 가능)

**요구사항**
- Blender 4.5 LTS 이상
- Windows 권장(우선 지원). macOS/Linux는 수동 경로 지정 시 동작 가능(자동검색 미지원)
- Clip Studio Paint 설치

**설치**
- 방법 A: ZIP 설치
  - 이 폴더(`clipstudio`) 전체를 ZIP으로 압축
  - Blender > `Edit > Preferences > Add-ons > Install...`
  - ZIP 선택 후 설치/활성화
- 방법 B: 로컬(개발용) 설치
  - 애드온 폴더에 본 폴더를 `clipstudio` 이름으로 배치
    - Windows: `%APPDATA%/Blender Foundation/Blender/<버전>/scripts/addons/`
    - macOS: `~/Library/Application Support/Blender/<버전>/scripts/addons/`
    - Linux: `~/.config/blender/<버전>/scripts/addons/`
  - Windows 개발 환경에서 링크(정션/심볼릭)로 연결하려면 `DEV_SETUP_WINDOWS.md` 참고

**처음 설정**
- 위치: `Edit > Preferences > Add-ons > Clip Studio Bridge`
- `클립 스튜디오 경로(Clip Studio Path)`를 지정하거나 `경로 자동 감지(Detect Path)` 버튼 사용
- `뷰포트에서 경로 설정 표시(Show Path Controls in Viewport)` 토글로 뷰포트 패널의 경로 UI 노출 제어
- `UI 언어(UI Language)`: Auto(OS)/English/한국어/日本語 선택 가능(콘솔 로그는 항상 영어)

**사용 위치**
- 3D Viewport > 사이드바(N) > `Clip Studio Bridge` 패널

**퀵 스타트**
- 활성 이미지 준비(다음 중 하나)
  - Texture Paint 캔버스, 또는
  - Image Editor의 활성 이미지, 또는
  - 머티리얼 노드의 활성 Image Texture 노드
- `Start Quick Edit (CSP)` 실행
  - 현재 뷰를 기준으로 임시 카메라(`CSP_QE_CAM_*`) 생성
  - 1:1 정사각 PNG로 캡처 후 CSP에서 자동으로 열기
- CSP에서 편집/저장(같은 파일에 저장)
- Blender로 돌아와 `Apply Projection (Active Obj)` 실행
  - 현재 뷰 시점 그대로 활성 오브젝트의 텍스처에 투영하여 EMIT 베이크로 반영
  - 임시 UV(`CSP_QE_TMP_UV`), UV Project 모디파이어(`CSP_QE_UVPROJECT`), 임시 머티리얼(`CSP_QE_TMP_MAT`)은 자동 관리/정리
- 필요 시 `Clean Temporary Files`로 캡처 파일/세션 리소스 정리(이전 씬 카메라도 복원)

**임시 파일/카메라**
- 저장 위치: Blender 임시 폴더(`bpy.app.tempdir`) 하위 `clipstudio/quickedit`
- 카메라: `CSP_QE_CAM_<타임스탬프>`
  - Start 시 기존 `CSP_QE_` 카메라가 있으면 삭제/유지/취소를 선택하는 확인 대화상자가 표시됩니다.

**알려진 제한 및 주의**
- UDIM/타일 이미지 미지원
- `Selected Objects` 대상 일괄 적용은 미구현(향후)
- 캡처는 뷰포트(OpenGL) 기반이며, 텍스처 색상 기준으로 Flat/Unlit에 가깝게 저장되고 오버레이는 비활성화됩니다.
- 프로젝션 시 렌더 엔진을 일시적으로 Cycles로 전환해 EMIT 베이크를 수행합니다.
- 캡처/베이크 해상도는 세션 기준 1:1 정사각으로 고정됩니다(기본 2048x2048).

**문제 해결**
- CSP 경로 미설정: Preferences에서 경로 지정 또는 `경로 자동 감지` 사용
- 활성 이미지 없음: Image Editor/Texture Paint/노드 에디터에서 활성 이미지를 선택
- 3D Viewport not found: 3D Viewport의 사이드바에서 버튼을 실행했는지 확인
- Source capture not found: CSP에서 편집본을 저장했는지 확인(임시 폴더 접근 권한 포함)
- 베이크 실패: 활성 오브젝트가 Mesh인지, Cycles 사용 가능 여부 확인

**호환성**
- Blender 4.5 LTS 이상
- Windows 우선 지원(경로 자동검색 포함). macOS/Linux는 경로 수동 지정으로 사용 가능

**버전**
- 0.1.0

**라이선스**
- 미명시 시 내부 사용 가정. 필요 시 `LICENSE` 추가 바랍니다.
