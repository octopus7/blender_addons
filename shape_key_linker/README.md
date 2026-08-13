# Shape Key Linker

[한국어](#한국어) · [English](#english) · [日本語](#日本語)

## 한국어

동일한 토폴로지의 외부 메시를 쉐이프 키에 연결하고 나중에 다시 업데이트하는 Blender 4.5+ 애드온입니다.

### 사용법

1. 원본으로 사용할 메시 오브젝트를 하나 이상 선택합니다.
2. 쉐이프 키를 받을 메시를 마지막으로 선택해 활성 오브젝트로 만듭니다.
3. Object Data Properties의 **Shape Keys** 패널 하단에서 **Join & Link as Shapes**를 누릅니다.
4. 원본 메시를 수정한 뒤 대상 메시만 활성화하고 **Update All**을 누릅니다.

각 연결 오른쪽의 새로고침 버튼을 누르면 해당 쉐이프 키만 업데이트됩니다. 연결은 오브젝트 이름이 아닌 Blender 오브젝트 참조로 `.blend` 파일에 저장되므로 원본이나 쉐이프 키의 이름을 바꿔도 유지됩니다.

**Live Update**를 켜면 원본 메시 변경을 감지해 활성화된 연결을 자동으로 갱신합니다. 토글은 기본적으로 꺼져 있으며, 켜진 동안 버튼이 강조 표시됩니다.

### 주의사항

- 원본과 대상은 정점 수와 정점 순서가 같은 토폴로지여야 합니다.
- 오브젝트의 위치, 회전, 스케일은 쉐이프 좌표에 반영하지 않습니다.
- 원본의 현재 평가 결과를 사용하므로 활성 쉐이프 키와 변형 모디파이어도 반영됩니다. 모디파이어가 정점 수를 바꾸면 업데이트되지 않습니다.
- **Unlink**는 연결만 제거하며 기존 쉐이프 키는 보존합니다.

### 라이선스

[MIT License](LICENSE)

---

## English

A Blender 4.5+ add-on that links external meshes with identical topology to shape keys and updates them later.

### Usage

1. Select one or more mesh objects to use as sources.
2. Select the mesh that will receive the shape keys last, making it the active object.
3. At the bottom of **Shape Keys** in Object Data Properties, click **Join & Link as Shapes**.
4. After editing a source mesh, activate only the target mesh and click **Update All**.

The refresh button on each link updates only that shape key. Links are stored in the `.blend` file as Blender object references rather than object names, so renaming a source or shape key does not break the link.

Turn on **Live Update** to detect source mesh changes and refresh enabled links automatically. The toggle is off by default and appears highlighted while enabled.

### Notes

- Source and target meshes must have identical vertex counts and vertex order.
- Object location, rotation, and scale are not applied to shape coordinates.
- The evaluated source is used, including active shape keys and deforming modifiers. A modifier that changes the vertex count prevents the update.
- **Unlink** removes only the link and preserves the existing shape key.

### License

[MIT License](LICENSE)

---

## 日本語

同一トポロジーの外部メッシュをシェイプキーにリンクし、後から更新できるBlender 4.5以降向けアドオンです。

### 使い方

1. ソースとして使用するメッシュオブジェクトを1つ以上選択します。
2. シェイプキーを受け取るメッシュを最後に選択し、アクティブオブジェクトにします。
3. Object Data Propertiesの**Shape Keys**下部で**Join & Link as Shapes**を押します。
4. ソースメッシュを編集した後、ターゲットメッシュだけをアクティブにして**Update All**を押します。

各リンク右側の更新ボタンを押すと、そのシェイプキーだけを更新できます。リンクはオブジェクト名ではなくBlenderのオブジェクト参照として`.blend`ファイルに保存されるため、ソースやシェイプキーの名前を変更しても維持されます。

**Live Update**をオンにすると、ソースメッシュの変更を検知して有効なリンクを自動更新します。初期設定はオフで、有効中はボタンが強調表示されます。

### 注意事項

- ソースとターゲットは頂点数と頂点順が同じトポロジーである必要があります。
- オブジェクトの位置、回転、スケールはシェイプ座標に反映されません。
- アクティブなシェイプキーや変形モディファイアを含む、評価済みのソースを使用します。頂点数を変更するモディファイアがある場合は更新できません。
- **Unlink**はリンクだけを解除し、既存のシェイプキーは残します。

### ライセンス

[MIT License](LICENSE)
