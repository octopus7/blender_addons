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
