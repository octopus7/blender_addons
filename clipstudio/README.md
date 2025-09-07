# Clip Studio Bridge (Blender Add-on)

블렌더용 Clip Studio 연동을 염두에 둔 기본 애드온 스켈레톤입니다. 현재는 동작 확인용 패널/오퍼레이터와 애드온 환경설정만 포함되어 있습니다.

## 설치 방법
- 방법 A: ZIP 설치
  1) 이 폴더(clipstudio) 전체를 ZIP으로 압축합니다.
  2) Blender > Edit > Preferences > Add-ons > Install...
  3) 생성한 ZIP 파일을 선택하고 설치/활성화합니다.

- 방법 B: 개발용 로컬 설치
  - `%APPDATA%/Blender Foundation/Blender/<버전>/scripts/addons/` (Windows)
  - `~/Library/Application Support/Blender/<버전>/scripts/addons/` (macOS)
  - `~/.config/blender/<버전>/scripts/addons/` (Linux)

  위 경로의 `addons` 폴더에 본 저장소 폴더 이름을 `clipstudio`로 두고 그대로 복사(또는 심볼릭 링크)하면 됩니다.
  - Windows 개발 환경에서 심볼릭/정션 링크로 연결하는 자세한 방법은 `DEV_SETUP_WINDOWS.md`를 참고하세요.

## 사용 위치
- 3D Viewport > Sidebar(N 키) > CSP QuickEdit 탭
- Preferences > Add-ons > Clip Studio Bridge 항목에서 CSP 실행 경로를 설정할 수 있습니다.

### Clip Studio Paint 연동
- CSP 경로 자동검색: Preferences 또는 CSP QuickEdit 탭에서 "CSP 경로 자동검색" 버튼 사용

메모
- 경로/폴더 해석은 Blender 유틸(`bpy.path.abspath`, `bpy.app.tempdir`)을 우선 사용합니다.
- 캡처 파일 저장 위치는 Blender 임시 폴더 하위 `clipstudio` 디렉터리이며, UI로 경로를 설정하지 않습니다.
- 뷰포트 패널의 CSP 경로/찾기 버튼 노출은 환경설정의 "뷰포트에 경로/찾기 표시"로 제어할 수 있습니다(기본: 표시).

### Quick Edit (CSP 전용)
- 위치: 3D Viewport > Sidebar(N) > "CSP QuickEdit" 탭
- Start: 현재 3D Viewport를 캡처해서 CSP로 엽니다.
- Apply Projection (Active Obj): CSP에서 저장한 캡처 파일을 자동으로 다시 읽고, 현재 뷰포트 시점 그대로 활성 오브젝트의 원본 텍스처에 투영 적용합니다.
- 임시파일 정리: 캡처 임시파일을 정리하고 세션을 종료합니다.

주의
- 패킹된 이미지는 Quick Edit 시작 시 임시 파일로 저장하여 편집합니다. Finish에서 "다시 패킹" 옵션으로 재패킹할 수 있습니다.
- UDIM/타일 이미지는 현재 범위에서 제외되어 있습니다.
 - 자동 프로젝션은 Blender 빌드에 따라 `paint.project_image` 오퍼레이터가 없을 수 있습니다. 이 경우 Texture Paint에서 수동 Project Paint를 사용하세요.

## 개발/리로드 팁
Blender 내부에서 모듈을 빠르게 리로드하려면 Python 콘솔 또는 텍스트 에디터에서 다음을 실행합니다:

```
import importlib, sys
m = sys.modules.get("clipstudio")
if m: importlib.reload(m)
else:
    import clipstudio
    importlib.reload(clipstudio)
```

## 다음 단계 제안
- 실제 Clip Studio 연동 시나리오 정의 (예: 이미지/PSD 내보내기, 레퍼런스 이미지 동기화 등)
- 파일/프로세스 실행 경로 유효성 검사 및 OS별 처리
- 작업 단축키, 상태표시, 오류 처리 추가
- 테스트 가능한 유닛으로 로직 분리 (UI, IO, 변환 등)
- Render Result 대신 뷰포트 캡처/멀티패스/컴포지터 결과 선택 옵션
- PSD 계층 구조 내보내기는 외부 라이브러리 필요 여부 검토

## 호환성
- 최소 지원: Blender 4.5 LTS 이상
- 현재 구현은 Windows 우선이며, macOS/Linux는 확장 가능 구조로 유지했습니다.

## 라이선스
- 명시되지 않은 경우 내부 사용 가정. 필요 시 LICENSE 추가 바랍니다.
