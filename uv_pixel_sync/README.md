# UV Pixel Sync

Blender 4.5+에서 선택한 UV 페이스와 그 아래 텍스처 픽셀을 함께 이동하는 애드온입니다. 이동량은 정수 픽셀로 스냅되며 픽셀을 보간하지 않습니다.

## 사용법

1. UV Editor에서 작업할 이미지를 선택합니다.
2. Mesh Edit Mode에서 완전한 UV 페이스 또는 아일랜드를 선택합니다.
3. `N` 사이드바의 **UV Pixel Sync** 탭을 엽니다.
4. **Move UV + Pixels**를 누르거나 `Ctrl+Shift+G`를 누릅니다.
5. 마우스로 이동하고 클릭 또는 `Enter`로 프리뷰를 만듭니다.
6. **Apply**로 원본 이미지 데이터에 반영하거나 **Cancel**로 취소합니다.
7. **Save Image**를 눌러 이미지 파일을 디스크에 저장합니다.

이동 중 `X`와 `Y`로 축을 제한할 수 있고 `Shift`로 미세 이동할 수 있습니다.

## 픽셀 옵션

- **Padding**: 선택 UV 주변에서 함께 이동할 픽셀 범위
- **Transparent / Black / Custom**: 이동 전 영역을 채우는 방법
- **Keep (Copy)**: 원본 픽셀을 남겨 복사처럼 동작
- **3D Material Preview**: 프리뷰 중 Image Texture 노드를 임시 이미지로 교체

## 제한사항

- 현재 버전은 이동만 지원합니다.
- 회전, 스케일, UDIM은 지원하지 않습니다.
- 선택 UV는 0-1 이미지 타일 안에 있어야 합니다.
- 프리뷰 중 메시 토폴로지와 UV 레이어를 변경하지 마세요.
- Apply는 Blender 이미지 데이터에 반영하며 실제 파일 저장은 **Save Image**가 필요합니다.

## 라이선스

[MIT License](LICENSE)
