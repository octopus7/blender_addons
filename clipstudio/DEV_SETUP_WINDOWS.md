# 개발용 설치 가이드 (Windows, 심볼릭/정션 링크)

Clip Studio Bridge 애드온을 개발 모드에서 즉시 반영되도록 사용하기 위한 Windows 전용 가이드입니다. Blender 4.5 LTS 이상을 기준으로 합니다.

## 개요
- 소스 폴더(본 저장소의 `clipstudio`)를 Blender의 `scripts/addons` 아래에 링크로 연결합니다.
- 디렉터리 정션(Junction, 권장) 또는 심볼릭 링크(Symbolic Link) 중 하나를 사용합니다.
  - Junction: 보통 관리자 권한 없이 생성 가능, NTFS 필요
  - Symlink: 관리자 권한 또는 Windows 개발자 모드 필요

## 경로 개념
- Blender 애드온 폴더: `%APPDATA%\Blender Foundation\Blender\4.5\scripts\addons`
- 이 저장소의 애드온 소스 폴더: `...\blender_addons\clipstudio` (폴더명은 반드시 `clipstudio`)

버전/폴더는 예시이므로, 실제 환경에 맞게 변경하세요.

## CMD(명령 프롬프트)에서 설정
1) 경로 변수 설정

```
set "BL_VER=4.5"
set "BL_ADDONS=%APPDATA%\Blender Foundation\Blender\%BL_VER%\scripts\addons"
set "SRC=D:\path\to\repo\blender_addons\clipstudio"
```

2) 애드온 폴더가 없으면 생성

```
mkdir "%BL_ADDONS%"
```

3) 링크 생성 (둘 중 하나 선택)
- 옵션 A: 디렉터리 정션(권장, 관리자 권한 불필요)

```
mklink /J "%BL_ADDONS%\clipstudio" "%SRC%"
```

- 옵션 B: 심볼릭 링크(관리자 권한 또는 개발자 모드 필요)

```
mklink /D "%BL_ADDONS%\clipstudio" "%SRC%"
```

4) 확인/활성화
- Blender 실행 → Edit > Preferences > Add-ons → "Clip Studio Bridge" 검색 후 활성화
- 3D Viewport의 사이드바(N)에서 "ClipStudio", "CSP QuickEdit" 탭 확인

5) 제거(링크만 삭제)

```
rmdir "%BL_ADDONS%\clipstudio"
```

## PowerShell에서 설정(대안)
1) 경로 변수 설정

```
$BL_VER = "4.5"
$BL_ADDONS = "$env:APPDATA/Blender Foundation/Blender/$BL_VER/scripts/addons"
$SRC = "D:/path/to/repo/blender_addons/clipstudio"
```

2) 애드온 폴더 생성

```
New-Item -ItemType Directory -Force -Path $BL_ADDONS | Out-Null
```

3) 링크 생성 (둘 중 하나 선택)
- 옵션 A: 정션(권장)

```
New-Item -ItemType Junction -Path "$BL_ADDONS/clipstudio" -Target $SRC
```

- 옵션 B: 심볼릭 링크(관리자 권한 또는 개발자 모드 필요)

```
New-Item -ItemType SymbolicLink -Path "$BL_ADDONS/clipstudio" -Target $SRC
```

4) 제거

```
Remove-Item -Force "$BL_ADDONS/clipstudio"
```

## 개발 루프 팁
- 코드 변경 후 즉시 반영:
  - Preferences에서 애드온 체크 해제/재체크 또는 F8(스크립트 리로드)
  - Python 콘솔에서 모듈 리로드:

```
import importlib, sys
m = sys.modules.get("clipstudio")
if m: importlib.reload(m)
else:
    import clipstudio
    importlib.reload(clipstudio)
```

## 포터블 Blender(선택)
- 포터블 설치를 쓰는 경우, 애드온 경로는 보통 `blender.exe`가 있는 폴더 아래 `4.5/scripts/addons`입니다.
- 예) `D:\apps\blender-4.5.0\4.5\scripts\addons\clipstudio`에 정션/심볼릭 링크 생성

## 문제 해결
- 애드온이 목록에 보이지 않음: 폴더명이 반드시 `clipstudio`인지, `__init__.py`가 존재하는지 확인
- 권한 문제로 링크 생성 실패: 정션(`/J`) 사용 또는 관리자 권한/개발자 모드 확인
- 경로에 공백 포함: 모든 경로를 큰따옴표로 감싸서 실행
- 버전 불일치: 본 애드온은 Blender 4.5 LTS 이상에서 동작하도록 설정됨

