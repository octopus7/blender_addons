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
- 3D Viewport > Sidebar(N 키) > ClipStudio 탭
- 패널의 "Say Hello" 버튼으로 애드온 동작을 빠르게 확인할 수 있습니다.
- Preferences > Add-ons > Clip Studio Bridge 항목에서 경로나 옵션을 설정할 수 있습니다.

### Clip Studio Paint 연동
- CSP 경로 자동검색: Preferences 또는 N 패널에서 "CSP 경로 자동검색" 버튼 사용
- 렌더 → CSP로 열기: 현재 씬을 렌더링하여 PNG/TIFF로 저장하고 Clip Studio Paint로 엽니다.
- 파일을 CSP로 열기: 파일 선택 대화상자에서 이미지/PSD/CLIP 파일을 선택해 바로 엽니다.

메모
- 경로/폴더 해석은 Blender 유틸(`bpy.path.abspath`, `bpy.app.tempdir`)을 우선 사용합니다.

### Quick Edit (CSP 전용)
- 위치: 3D Viewport > Sidebar(N) > "CSP QuickEdit" 탭
- Start: 활성 이미지(텍스처 페인트 캔버스/이미지 에디터/활성 이미지 텍스처 노드 순)를 외부 편집기로 오픈
  - 원본 파일이 존재하면 그 경로를 그대로 사용, 없거나 패킹된 경우 임시 파일로 저장 후 사용
- Reload: 외부에서 저장된 내용을 블렌더 이미지에 재불러오기
- Finish: 필요 시 수정본을 원래 경로에 덮어쓰고(옵션) 패킹되었던 경우 재패킹(옵션), 임시파일 정리(옵션)

주의
- 패킹된 이미지는 Quick Edit 시작 시 임시 파일로 저장하여 편집합니다. Finish에서 "다시 패킹" 옵션으로 재패킹할 수 있습니다.
- UDIM/타일 이미지는 현재 범위에서 제외되어 있습니다.

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
