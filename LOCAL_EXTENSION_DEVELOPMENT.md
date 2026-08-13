# Blender 익스텐션을 로컬 저장소로 연결해 개발하기

Windows에서 정션이나 심볼릭 링크를 만들지 않고, Git 작업 폴더를 Blender의 **Local Repository**로 직접 등록하는 방법이다.

이 프로젝트는 Blender 4.5 이상을 대상으로 한다.

## 핵심 요약

Blender에 아래 폴더를 로컬 저장소로 등록한다.

```text
D:\github\blender_addons
```

`shape_key_linker` 폴더 자체를 지정하면 안 된다. 로컬 저장소 경로 바로 아래에 각 익스텐션 폴더가 있어야 한다.

```text
D:\github\blender_addons\
├─ shape_key_linker\
│  ├─ blender_manifest.toml
│  ├─ __init__.py
│  └─ addon.py
└─ ...다른 익스텐션 폴더
```

로컬 저장소는 소스 폴더를 Blender가 직접 읽는 방식이다. 따라서 개발할 때 `dist` ZIP을 빌드하거나 `index.json`을 만들 필요가 없다.

## 처음 한 번 설정하기

1. Blender에서 **Edit → Preferences**를 연다.
2. **Get Extensions** 탭으로 이동한다.
3. 오른쪽 위의 **Repositories** 메뉴를 연다.
4. `+` 버튼을 누르고 **Add Local Repository**를 선택한다.
5. 다음과 같이 입력한다.

   - **Name**: `Blender Add-ons Dev`
   - **Custom Directory**: 켬
   - **Directory**: `D:\github\blender_addons`

6. **Create**를 누른다.
7. Preferences의 **Add-ons** 탭에서 `Shape Key Linker`를 검색한다.
8. 체크박스를 켜서 익스텐션을 활성화한다.
9. 익스텐션 상세 정보의 설치 경로가 `D:\github\blender_addons\shape_key_linker`인지 확인한다.

이제 Blender는 Git 작업 폴더의 소스를 직접 사용한다. 파일을 별도 애드온 폴더로 복사하거나 정션을 만들 필요가 없다.

## 평소 개발 순서

1. `shape_key_linker` 안의 Python 파일을 수정하고 저장한다.
2. Blender에서 **Edit → Preferences → Add-ons**를 연다.
3. Add-ons 설정 메뉴에서 **Refresh Local**을 실행한다.
4. `F3`를 누르고 **Reload Scripts**를 실행한다.
5. 변경된 기능을 테스트한다.

`Refresh Local`은 로컬 익스텐션과 메타데이터의 변경을 다시 스캔한다. 이미 import된 Python 코드와 실행 중인 상태까지 항상 완전히 초기화하는 것은 아니므로, 변경이 반영되지 않거나 등록 관련 오류가 나면 Blender를 재시작하는 것이 가장 확실하다.

특히 다음을 수정했을 때는 재시작하는 편이 안전하다.

- `register()` 또는 `unregister()`
- `PropertyGroup`, `Operator`, `Panel` 같은 등록 클래스
- 핸들러, 타이머 또는 키맵
- `blender_manifest.toml`
- 이미 import된 하위 모듈의 전역 상태

## 명령줄로 저장소 등록하기

UI 대신 PowerShell에서도 등록할 수 있다. 사용자 설정이 동시에 덮어써지는 일을 피하려면 Blender를 닫은 상태에서 실행한다.

```powershell
$Blender = "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"

& $Blender --command extension repo-add blender_addons_dev `
  --name "Blender Add-ons Dev" `
  --directory "D:\github\blender_addons"

& $Blender --command extension repo-list
```

`--url`을 지정하지 않아야 외부 서버와 연결되지 않은 로컬 저장소가 된다.

등록을 제거할 때는 다음 명령을 사용한다. 소스 코드 폴더를 지우는 명령은 아니다.

```powershell
& $Blender --command extension repo-remove blender_addons_dev
```

## 보이지 않거나 반영되지 않을 때

### 익스텐션이 목록에 없음

- 저장소 경로가 `D:\github\blender_addons`인지 확인한다.
- `D:\github\blender_addons\shape_key_linker\blender_manifest.toml`이 존재하는지 확인한다.
- **Refresh Local**을 실행한다.
- 이 익스텐션은 `blender_version_min = "4.5.0"`이므로 Blender 4.5 이상에서 연다.
- Blender 콘솔에 manifest 또는 Python 오류가 있는지 확인한다.

### 파일을 수정했는데 예전 코드가 실행됨

- `F3 → Reload Scripts`를 실행한다.
- Add-ons에서 익스텐션을 껐다가 다시 켠다.
- 그래도 남아 있으면 Blender를 재시작한다.
- 익스텐션 상세 정보에서 다른 위치에 설치된 같은 ID의 복사본을 사용 중이지 않은지 확인한다.

### 같은 익스텐션이 중복으로 나타남

기존에 ZIP으로 설치한 `shape_key_linker`가 다른 저장소에 남아 있을 수 있다. 상세 정보의 경로를 확인하고, 개발 폴더가 아닌 복사본은 비활성화하거나 제거한다.

## 이 방식에서 필요 없는 작업

로컬 소스 개발 중에는 다음 작업이 필요 없다.

- Windows 정션 또는 심볼릭 링크 생성
- 소스를 Blender 사용자 애드온 폴더로 복사
- 매 수정마다 익스텐션 ZIP 빌드
- `server-generate`로 `index.json` 생성
- `file:///.../index.json` 원격 저장소 등록

ZIP 빌드와 정적 저장소 인덱스는 배포 패키지를 검사하거나 다른 사람에게 업데이트 저장소를 제공할 때 사용한다.

## 공식 문서

- [Blender 4.5 Extensions 환경설정](https://docs.blender.org/manual/en/4.5/editors/preferences/extensions.html)
- [Blender 4.5 Extensions 명령줄 인자](https://docs.blender.org/manual/en/4.5/advanced/command_line/extension_arguments.html)
- [Blender 4.5 익스텐션 만들기](https://docs.blender.org/manual/en/4.5/advanced/extensions/getting_started.html)
- [정적 Extensions 저장소 만들기](https://docs.blender.org/manual/en/4.5/advanced/extensions/creating_repository/static_repository.html)
