# Blender Add-ons

[한국어](#한국어) · [English](#english) · [日本語](#日本語)

[최신 릴리스 다운로드 · Download the latest release · 最新リリースをダウンロード](https://github.com/octopus7/blender_addons/releases/latest)

## 한국어

Blender 애드온을 모아 관리하는 저장소입니다.

### Shape Key Linker

동일한 토폴로지의 외부 메시를 쉐이프 키에 연결하고, 나중에 원본 메시의 변경 사항을 다시 가져오는 Blender 4.5+ 애드온입니다. 연결 정보는 `.blend` 파일에 저장되므로 원본 메시를 다시 선택할 필요가 없습니다.

#### 사용법

1. 쉐이프 키 원본으로 사용할 메시를 하나 이상 선택합니다.
2. 쉐이프 키를 받을 대상 메시를 마지막으로 선택해 활성 오브젝트로 만듭니다.
3. **Object Data Properties → Shape Keys → Shape Key Linker**에서 **Join & Link as Shapes**를 누릅니다.
4. 원본 메시를 수정한 뒤 대상 메시에서 **Update All**을 누릅니다.

- 각 연결 오른쪽의 새로고침 버튼은 해당 페어만 업데이트합니다.
- **Live Update**를 켜면 원본 메시 변경을 감지해 활성화된 연결을 자동으로 갱신합니다. 기본값은 꺼짐입니다.
- 체크박스를 끄면 해당 연결을 **Update All**과 **Live Update**에서 제외합니다.
- `X` 버튼은 쉐이프 키를 유지하고 연결만 해제합니다.
- 원본과 대상은 정점 수와 정점 순서가 같은 토폴로지여야 합니다.

자세한 내용은 [Shape Key Linker 문서](shape_key_linker/README.md)를 참고하세요.

### UV Pixel Sync

UV Editor에서 선택한 UV 페이스와 그 아래의 텍스처 픽셀을 함께 이동하는 Blender 4.5+ 애드온입니다. 이동량을 정수 픽셀 단위로 제한해 픽셀 아트와 저해상도 텍스처가 보간되는 것을 방지합니다.

이동 중에는 별도의 미리보기 이미지를 사용하므로 원본 이미지 데이터가 즉시 변경되지 않습니다. 위치를 확인한 뒤 **Apply**로 반영하거나 **Cancel**로 UV와 이미지를 원래 상태로 되돌릴 수 있습니다.

#### 사용법

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

### 릴리스 규칙

이 저장소의 GitHub 릴리스는 여러 애드온을 한 번에 묶어 배포하므로, 태그에는 개별 애드온 버전 대신 날짜를 사용합니다.

- 태그: `release-YYYY.MM.DD` (예: `release-2026.08.14`)
- 같은 날 다시 배포할 경우: `release-YYYY.MM.DD-2`
- 릴리스 제목: `Blender Add-ons — YYYY.MM.DD`

각 애드온의 실제 버전은 해당 폴더의 `blender_manifest.toml`에서 별도로 관리합니다. 배포 ZIP도 이 값을 사용해 `애드온_ID-버전.zip` 형식으로 생성됩니다. 예: `shape_key_linker-1.1.8.zip`, `uv_pixel_sync-1.0.0.zip`.

### 라이선스

이 저장소 전체는 [MIT License](LICENSE)로 배포됩니다.

---

## English

This repository contains a collection of Blender add-ons.

### Shape Key Linker

A Blender 4.5+ add-on that links external meshes with identical topology to shape keys and lets you pull in later changes from the source meshes. Links are stored in the `.blend` file, so the source meshes do not need to be selected again.

#### Usage

1. Select one or more meshes to use as shape-key sources.
2. Select the target mesh last so that it becomes the active object.
3. Open **Object Data Properties → Shape Keys → Shape Key Linker** and click **Join & Link as Shapes**.
4. After editing a source mesh, activate the target mesh and click **Update All**.

- The refresh button on each link updates only that pair.
- Turn on **Live Update** to refresh enabled links automatically when a source mesh changes. It is off by default.
- Clear a link's checkbox to exclude it from **Update All** and **Live Update**.
- The `X` button removes only the link and preserves the shape key.
- Source and target meshes must have the same vertex count and vertex order.

See the [Shape Key Linker documentation](shape_key_linker/README.md) for details.

### UV Pixel Sync

A Blender 4.5+ add-on that moves selected UV faces together with the texture pixels beneath them. Movement is restricted to whole-pixel increments to prevent interpolation in pixel art and low-resolution textures.

Movement uses a separate preview image, leaving the original image data unchanged until you confirm. Use **Apply** to commit the result or **Cancel** to restore the original UVs and image.

#### Usage

1. Select an image in the UV Editor and enter Mesh Edit Mode.
2. Select the UV faces or islands to move.
3. In the `N` sidebar, open **UV Pixel Sync** and click **Move UV + Pixels**.
4. Move with the mouse, then click or press `Enter` to confirm the preview. Use `X`/`Y` to constrain an axis and `Shift` for fine movement.
5. Click **Apply** to update the image data, then **Save Image** to write the file.

- **Padding** includes neighboring pixels around the selected UVs.
- The vacated source area can be filled with transparency, black, or a custom color.
- **Keep (Copy)** preserves the source pixels and copies them to the new location.
- The current version supports translation within the 0–1 UV tile. Rotation, scaling, and UDIM are not supported.

See the [UV Pixel Sync documentation](uv_pixel_sync/README.md) for details.

### Release convention

Each GitHub release packages all add-ons together, so release tags use a date instead of an individual add-on version.

- Tag: `release-YYYY.MM.DD` (example: `release-2026.08.14`)
- Additional release on the same day: `release-YYYY.MM.DD-2`
- Release title: `Blender Add-ons — YYYY.MM.DD`

Each add-on keeps its own version in `blender_manifest.toml`. Distribution archives use the format `add-on_ID-version.zip`, for example `shape_key_linker-1.1.8.zip` and `uv_pixel_sync-1.0.0.zip`.

### License

This entire repository is distributed under the [MIT License](LICENSE).

---

## 日本語

Blenderアドオンをまとめて管理するリポジトリです。

### Shape Key Linker

同一トポロジーの外部メッシュをシェイプキーにリンクし、後からソースメッシュの変更を取り込めるBlender 4.5以降向けアドオンです。リンク情報は`.blend`ファイルに保存されるため、更新時にソースメッシュを選択し直す必要はありません。

#### 使い方

1. シェイプキーのソースにするメッシュを1つ以上選択します。
2. シェイプキーを受け取るターゲットメッシュを最後に選択し、アクティブオブジェクトにします。
3. **Object Data Properties → Shape Keys → Shape Key Linker**で**Join & Link as Shapes**を押します。
4. ソースメッシュを編集した後、ターゲットメッシュで**Update All**を押します。

- 各リンク右側の更新ボタンは、そのペアだけを更新します。
- **Live Update**をオンにすると、ソースメッシュの変更を検知して有効なリンクを自動更新します。初期設定はオフです。
- チェックを外すと、そのリンクは**Update All**と**Live Update**の対象外になります。
- `X`ボタンはリンクだけを解除し、シェイプキーは残します。
- ソースとターゲットは頂点数と頂点順が同じトポロジーである必要があります。

詳細は[Shape Key Linkerドキュメント](shape_key_linker/README.md)を参照してください。

### UV Pixel Sync

選択したUVフェイスと、その下にあるテクスチャのピクセルを一緒に移動するBlender 4.5以降向けアドオンです。移動量を整数ピクセル単位に制限し、ピクセルアートや低解像度テクスチャの補間を防ぎます。

移動中は別のプレビュー画像を使用するため、確定するまで元画像のデータは変更されません。**Apply**で反映し、**Cancel**でUVと画像を元の状態に戻せます。

#### 使い方

1. UV Editorで画像を選択し、Mesh Edit Modeに入ります。
2. 移動するUVフェイスまたはアイランドを選択します。
3. `N`サイドバーの**UV Pixel Sync**で**Move UV + Pixels**を押します。
4. マウスで移動し、クリックまたは`Enter`でプレビューを確定します。`X`/`Y`で軸を固定し、`Shift`で微調整できます。
5. **Apply**で画像データに反映した後、**Save Image**でファイルを保存します。

- **Padding**で選択UVの周囲にあるピクセルも一緒に移動できます。
- 移動元の領域は透明、黒、または任意の色で塗りつぶせます。
- **Keep (Copy)**では元のピクセルを残したまま、新しい位置へコピーします。
- 現在のバージョンは0–1 UVタイル内の移動のみ対応しています。回転、拡大縮小、UDIMには対応していません。

詳細は[UV Pixel Syncドキュメント](uv_pixel_sync/README.md)を参照してください。

### リリース規則

GitHubリリースでは複数のアドオンをまとめて配布するため、タグには個別アドオンのバージョンではなく日付を使用します。

- タグ: `release-YYYY.MM.DD`（例: `release-2026.08.14`）
- 同じ日に再配布する場合: `release-YYYY.MM.DD-2`
- リリースタイトル: `Blender Add-ons — YYYY.MM.DD`

各アドオンのバージョンは、それぞれの`blender_manifest.toml`で管理します。配布ZIPは`アドオンID-バージョン.zip`形式で生成されます。例: `shape_key_linker-1.1.8.zip`、`uv_pixel_sync-1.0.0.zip`。

### ライセンス

このリポジトリ全体は[MIT License](LICENSE)で配布されます。
