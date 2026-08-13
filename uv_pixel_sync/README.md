# UV Pixel Sync

[한국어](#한국어) · [English](#english) · [日本語](#日本語)

## 한국어

Blender 4.5+에서 선택한 UV 페이스와 그 아래 텍스처 픽셀을 함께 이동하는 애드온입니다. 이동량은 정수 픽셀로 스냅되며 픽셀을 보간하지 않습니다.

### 사용법

1. UV Editor에서 작업할 이미지를 선택합니다.
2. Mesh Edit Mode에서 완전한 UV 페이스 또는 아일랜드를 선택합니다.
3. `N` 사이드바의 **UV Pixel Sync** 탭을 엽니다.
4. **Move UV + Pixels**를 누르거나 `Ctrl+Shift+G`를 누릅니다.
5. 마우스로 이동하고 클릭 또는 `Enter`로 미리보기를 확정합니다.
6. **Apply**로 원본 이미지 데이터에 반영하거나 **Cancel**로 취소합니다.
7. **Save Image**를 눌러 이미지 파일을 디스크에 저장합니다.

이동 중 `X`와 `Y`로 축을 제한할 수 있고 `Shift`로 미세 이동할 수 있습니다.

### 픽셀 옵션

- **Padding**: 선택 UV 주변에서 함께 이동할 픽셀 범위
- **Transparent / Black / Custom**: 이동한 원본 영역을 채우는 방법
- **Keep (Copy)**: 원본 픽셀을 유지하고 새 위치로 복사
- **3D Material Preview**: 미리보기 중 Image Texture 노드를 임시 이미지로 교체

### 제한사항

- 현재 버전은 이동만 지원합니다.
- 회전, 크기 조절, UDIM은 지원하지 않습니다.
- 선택 UV는 0–1 이미지 타일 안에 있어야 합니다.
- 미리보기 중 메시 토폴로지와 UV 레이어를 변경하지 마세요.
- **Apply**는 Blender 이미지 데이터에 반영합니다. 실제 파일을 저장하려면 **Save Image**가 필요합니다.

### 라이선스

[MIT License](LICENSE)

---

## English

A Blender 4.5+ add-on that moves selected UV faces together with the texture pixels beneath them. Movement snaps to whole pixels and does not interpolate pixel values.

### Usage

1. Select the image to edit in the UV Editor.
2. In Mesh Edit Mode, select complete UV faces or islands.
3. Open the **UV Pixel Sync** tab in the `N` sidebar.
4. Click **Move UV + Pixels** or press `Ctrl+Shift+G`.
5. Move with the mouse, then click or press `Enter` to confirm the preview.
6. Use **Apply** to write to the original image data or **Cancel** to discard the preview.
7. Click **Save Image** to save the image file to disk.

Press `X` or `Y` while moving to constrain an axis, and hold `Shift` for fine movement.

### Pixel options

- **Padding**: Number of neighboring pixels included around the selected UVs
- **Transparent / Black / Custom**: How the vacated source area is filled
- **Keep (Copy)**: Preserve the source pixels and copy them to the new location
- **3D Material Preview**: Temporarily replace matching Image Texture nodes with the preview image

### Limitations

- The current version supports translation only.
- Rotation, scaling, and UDIM are not supported.
- Selected UVs must remain inside the 0–1 image tile.
- Do not change mesh topology or the UV layer during a preview.
- **Apply** updates Blender's image data. Use **Save Image** to write the actual file.

### License

[MIT License](LICENSE)

---

## 日本語

選択したUVフェイスと、その下にあるテクスチャのピクセルを一緒に移動するBlender 4.5以降向けアドオンです。移動量は整数ピクセルにスナップされ、ピクセル値は補間されません。

### 使い方

1. UV Editorで編集する画像を選択します。
2. Mesh Edit Modeで完全なUVフェイスまたはアイランドを選択します。
3. `N`サイドバーの**UV Pixel Sync**タブを開きます。
4. **Move UV + Pixels**を押すか、`Ctrl+Shift+G`を押します。
5. マウスで移動し、クリックまたは`Enter`でプレビューを確定します。
6. **Apply**で元画像のデータに反映するか、**Cancel**でプレビューを破棄します。
7. **Save Image**を押して画像ファイルをディスクに保存します。

移動中に`X`または`Y`で軸を固定し、`Shift`で微調整できます。

### ピクセルオプション

- **Padding**: 選択UVの周囲で一緒に移動するピクセル範囲
- **Transparent / Black / Custom**: 移動元の領域を塗りつぶす方法
- **Keep (Copy)**: 元のピクセルを残したまま新しい位置へコピー
- **3D Material Preview**: プレビュー中、対応するImage Textureノードを一時画像に置き換え

### 制限事項

- 現在のバージョンは移動のみ対応しています。
- 回転、拡大縮小、UDIMには対応していません。
- 選択UVは0–1画像タイル内にある必要があります。
- プレビュー中にメッシュのトポロジーやUVレイヤーを変更しないでください。
- **Apply**はBlenderの画像データを更新します。実際のファイルを保存するには**Save Image**を使用してください。

### ライセンス

[MIT License](LICENSE)
