# Blender Add-ons

Blender 애드온을 모아 관리하는 저장소입니다.

## Shape Key Linker

동일한 토폴로지의 외부 메시를 쉐이프 키에 연결하고, 나중에 원본 메시의 변경 사항을 다시 가져오는 Blender 4.5용 애드온입니다. 연결 정보는 `.blend` 파일에 저장되므로 원본 메시를 다시 선택할 필요가 없습니다.

[최신 릴리즈 다운로드](https://github.com/octopus7/blender_addons/releases/latest)

### 사용법

1. 쉐이프 키 원본으로 사용할 메시를 하나 이상 선택합니다.
2. 쉐이프 키를 받을 대상 메시를 마지막으로 선택해 활성 오브젝트로 만듭니다.
3. **Object Data Properties → Shape Keys → Shape Key Linker**에서 **Join & Link as Shapes**를 누릅니다.
4. 원본 메시를 수정한 뒤 대상 메시에서 **Update All**을 누릅니다.

- 각 연결 오른쪽의 새로고침 버튼은 해당 페어만 업데이트합니다.
- 체크박스를 끄면 해당 연결을 **Update All**에서 제외합니다.
- `X` 버튼은 쉐이프 키를 유지하고 연결만 해제합니다.
- 원본과 대상은 정점 수와 정점 순서가 같은 토폴로지여야 합니다.

자세한 내용은 [Shape Key Linker 문서](shape_key_linker/README.md)를 참고하세요.

## UV Pixel Sync

UV Editor에서 선택한 UV 페이스와 그 아래의 텍스처 픽셀을 함께 이동하는 Blender 4.5+ 애드온입니다. UV만 옮겨 텍스처 위치가 어긋나는 상황을 줄이고, 이동량을 정수 픽셀 단위로 제한해 픽셀 아트와 저해상도 텍스처가 보간되는 것을 방지합니다.

이동 중에는 별도의 미리보기 이미지를 사용하므로 원본 이미지 데이터가 즉시 변경되지 않습니다. 위치를 확인한 뒤 **Apply**로 반영하거나 **Cancel**로 UV와 이미지를 원래 상태로 되돌릴 수 있습니다.

### 사용법

1. UV Editor에서 이미지를 선택하고 Mesh Edit Mode로 들어갑니다.
2. 이동할 UV 페이스 또는 아일랜드를 선택합니다.
3. `N` 사이드바의 **UV Pixel Sync**에서 **Move UV + Pixels**를 누릅니다.
4. 마우스로 이동하고 클릭 또는 `Enter`로 미리보기를 확정합니다. `X`/`Y`는 축 제한, `Shift`는 미세 이동입니다.
5. **Apply**로 이미지 데이터에 반영한 뒤 **Save Image**로 파일을 저장합니다.

- **Padding**으로 선택한 UV 주변 픽셀까지 함께 이동할 수 있습니다.
- 이동한 원본 영역을 투명색, 검은색 또는 사용자 지정 색상으로 채울 수 있습니다.
- **Keep (Copy)**를 사용하면 원본 픽셀을 유지한 채 새 위치로 복사합니다.
- 현재 버전은 0–1 UV 타일의 이동만 지원하며 회전, 크기 조절, UDIM은 지원하지 않습니다.

자세한 내용은 [UV Pixel Sync 문서](uv_pixel_sync/README.md)를 참고하세요.

## 릴리스 규칙

이 저장소의 GitHub 릴리스는 여러 애드온을 한 번에 묶어 배포하므로, 태그에는 개별 애드온 버전 대신 날짜를 사용합니다.

- 태그: `release-YYYY.MM.DD` (예: `release-2026.08.14`)
- 같은 날 다시 배포할 경우: `release-YYYY.MM.DD-2`
- 릴리스 제목: `Blender Add-ons — YYYY.MM.DD`

각 애드온의 실제 버전은 해당 폴더의 `blender_manifest.toml`에서 별도로 관리합니다. 배포 ZIP도 이 값을 사용해 `애드온_ID-버전.zip` 형식으로 생성됩니다. 예: `shape_key_linker-1.1.7.zip`, `uv_pixel_sync-1.0.0.zip`.

## License

이 저장소 전체는 [MIT License](LICENSE)로 배포됩니다.
