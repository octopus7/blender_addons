# Shape Key Linker Improvement Plan

이 문서는 Shape Key Linker의 Live Update 성능과 안정성을 개선하기 위한 작업 계획이다. 구현 세부 코드는 포함하지 않으며, 각 단계의 범위와 완료 조건을 정의한다.

## 목표

- 원본 Source 하나를 수정할 때 관련된 Link만 갱신한다.
- 동일 Source의 evaluated mesh를 한 번만 계산해 여러 Link에서 재사용한다.
- 대형 씬에서 depsgraph 감지 비용을 줄인다.
- Live Update 실패 원인을 UI에서 확인할 수 있게 한다.
- Shape Key를 잘못 식별해 다른 키를 덮어쓰는 상황을 방지한다.
- Blender 4.5, 5.0, 5.2 호환성을 유지한다.

## 설계 원칙

- depsgraph handler에서는 데이터를 수정하지 않고 변경 사항만 기록한다.
- 실제 Shape Key 갱신은 debounce timer에서 수행한다.
- 성능 최적화보다 데이터 오염 방지를 우선한다.
- 식별이 모호하면 자동 복구하지 않고 명확한 오류 상태로 중단한다.
- 캐시는 `.blend` 파일의 실제 링크 데이터를 대체하지 않는다.
- Load, Undo, Redo, Object 삭제 후에도 캐시를 안전하게 재구축할 수 있어야 한다.

## Phase 1 — Live Update 실행 단위 개선

### 1. Target Edit Mode 재시도 개선

현재 Target이 Edit Mode이면 timer가 약 0.1초마다 계속 재시도할 수 있다.

작업:

- Target Edit Mode에서 지속적으로 timer를 호출하지 않도록 변경한다.
- 갱신 요청은 보존하되 Object Mode 복귀 또는 다음 관련 depsgraph 이벤트에서 다시 예약한다.
- 장시간 Edit Mode에서도 불필요한 polling이 발생하지 않아야 한다.

완료 조건:

- Target이 Edit Mode인 동안 timer가 초당 반복 실행되지 않는다.
- Object Mode로 돌아오면 보류된 갱신이 한 번 실행된다.

### 2. Dirty Target을 Dirty Source/Link 구조로 변경

작업:

- 변경된 Source와 그 Source에 연결된 Link만 dirty 상태로 기록한다.
- 하나의 Source 변경으로 같은 Target의 다른 Link가 갱신되지 않게 한다.
- Link 삭제 또는 비활성화 후 남은 dirty 항목을 안전하게 무시한다.

권장 개념 구조:

```text
Changed Source
└─ Target A / Link 1
└─ Target B / Link 4
```

완료 조건:

- 100개 Link 중 Source 하나를 변경했을 때 관련 `_update_link` 경로만 실행된다.
- 비활성 Link는 Live Update 대상에서 제외된다.

### 3. Source 평가 결과 공유

작업:

- Source의 `evaluated_get()`과 `to_mesh()`를 dirty Source마다 한 번만 수행한다.
- 얻은 좌표 배열을 연결된 여러 Target Shape Key에 재사용한다.
- Source 평가와 Target Shape Key 쓰기 단계를 분리한다.

완료 조건:

- 동일 Source가 여러 Target에 연결돼도 한 번의 timer 처리에서 evaluated mesh 생성 횟수는 1회다.
- 각 Target의 정점 수 검사는 독립적으로 수행된다.

## Phase 2 — Reverse Lookup과 캐시 수명 관리

### 4. Source → Link Reverse Lookup

작업:

- Source Object 또는 Source Mesh를 key로 관련 Target/Link를 찾는 runtime cache를 구성한다.
- depsgraph 이벤트마다 `bpy.data.objects` 전체를 순회하지 않게 한다.
- Target pointer를 다시 찾기 위한 별도의 전체 Object 순회도 제거한다.

캐시 재구축 시점:

- Add-on 등록
- 파일 Load
- Undo / Redo
- Link 추가 및 삭제
- Live Update 활성화 및 비활성화
- Source 또는 Target 삭제

완료 조건:

- Shape Key Linker와 관계없는 Object 변경 시 전체 Object 순회가 발생하지 않는다.
- 캐시가 유실되거나 오래된 경우 실제 저장 데이터에서 복구할 수 있다.
- 캐시 오류가 링크 데이터 손상으로 이어지지 않는다.

## Phase 3 — 상태와 오류 표시

### 5. Link Runtime Status 도입

표시할 상태 후보:

- `READY`
- `UPDATED`
- `MISSING_SOURCE`
- `MISSING_SHAPE_KEY`
- `VERTEX_COUNT_MISMATCH`
- `EVALUATED_TOPOLOGY_MISMATCH`
- `AMBIGUOUS_SHAPE_KEY`
- `UPDATE_ERROR`

작업:

- Live Update의 성공 여부와 오류 메시지를 버리지 않고 runtime 상태에 기록한다.
- UI 아이콘과 tooltip으로 마지막 실패 원인을 표시한다.
- 원본 Mesh 정점 수와 evaluated mesh 정점 수 불일치를 구분한다.
- 마지막 성공 시간 표시는 선택 기능으로 검토한다.

주의:

- 상태 갱신 때문에 `.blend` 파일이 불필요하게 수정되거나 depsgraph 재호출이 발생하지 않도록 한다.
- 가능한 경우 저장 Property보다 runtime cache를 사용한다.

완료 조건:

- Live Update 실패 시 사용자가 원인을 UI에서 확인할 수 있다.
- 수동 Update와 Live Update가 동일한 오류 분류를 사용한다.

## Phase 4 — Shape Key 식별 안정성

### 6. 모호한 Index 복구 차단

현재 Name, Index, 전체 Key 개수 조합은 삭제와 삽입이 동시에 발생하면 다른 Shape Key를 잘못 가리킬 수 있다.

작업:

- 이름으로 찾지 못한 경우 Index fallback의 신뢰 조건을 강화한다.
- 삭제, 삽입, 재정렬이 의심되면 자동으로 다른 Key를 선택하지 않는다.
- 모호한 상태는 `AMBIGUOUS_SHAPE_KEY`로 표시하고 갱신을 중단한다.

완료 조건:

- 잘못된 Shape Key를 정상 링크로 판단해 덮어쓰는 테스트가 모두 차단된다.
- 단순 Rename은 가능한 범위에서 계속 추적한다.

### 7. Persistent Identity 방식 조사

Blender 4.5~5.2의 `KeyBlock`은 Custom Property 쓰기를 지원하지 않으므로 KeyBlock에 UUID를 직접 저장하는 방식은 사용하지 않는다.

조사 대상:

- Key datablock 또는 Target Object에 별도 mapping table 저장
- 런타임 KeyBlock pointer와 저장된 Name/Index의 결합
- Rename 및 Reorder 감지 규칙
- Blender 외부 기능으로 Key가 수정됐을 때의 복구 가능성

진행 조건:

- 단순 Index fallback보다 명확하게 안전한 방식이 확인될 때만 도입한다.
- 완전한 식별이 불가능하면 실패 안전 방식 유지가 우선이다.

## Phase 5 — 선택적 토폴로지 검증

### 8. Connectivity Validation

작업:

- Link 생성 시 선택적으로 연결 구조를 검사한다.
- 검사 후보는 Vertex, Edge, Polygon, Loop 개수와 정점 인덱스 기반 연결 구조다.
- 순서 변화에 영향을 받지 않도록 Edge pair 등은 정규화해 hash를 계산한다.
- Live Update마다 전체 검사를 반복하지 않는다.
- 별도의 Validate 명령으로 다시 검사할 수 있게 한다.

주의:

- 연결 구조 검사는 정점의 의미적 대응을 완전히 증명하지 못한다.
- UI에서는 완전한 Vertex Order 보장으로 과장하지 않는다.

완료 조건:

- Vertex Count는 같지만 연결 구조가 다른 대표 사례를 검출한다.
- 대형 메시의 최초 Link 시간을 과도하게 증가시키지 않는다.

## Phase 6 — Dependency Cycle 방지

### 9. Live Link Cycle Detection

작업:

- Source → Target 의존 관계 그래프를 구성한다.
- Live Update 활성 Link에 대해 직접 및 간접 순환을 검사한다.
- 순환을 만드는 Link 생성 또는 Live 활성화를 거부하고 이유를 표시한다.

검사 사례:

```text
A → B → A
A → B → C → A
```

완료 조건:

- 순환 관계가 depsgraph 이벤트 사이에서 반복 갱신을 만들지 않는다.
- 순환과 관계없는 수동 업데이트 워크플로에 불필요한 제한을 두지 않는다.

## Phase 7 — 후속 UX

핵심 성능과 안정성 작업 이후 필요성을 다시 평가한다.

- Source 선택
- Source를 선택하고 Frame Selected
- 여러 Target의 Live Update를 일시 정지하는 전역 Pause
- 마지막 성공 갱신 시간

현재 기능과 중복되므로 별도 추가하지 않는 항목:

- Update Selected Link: 각 Link 오른쪽 새로고침 버튼으로 이미 제공
- Update Dirty: debounce 후 자동 처리되므로 사용자 명령으로서 의미가 불분명
- Target별 Pause: 현재 Live Update 토글이 해당 역할을 수행

Auto Layout은 핵심 Link 기능과 독립적인 별도 기능으로만 검토한다.

## 테스트 계획

### 성능 및 Granularity

- Target 1개, Link 100개, 변경 Source 1개에서 관련 Link만 갱신
- 동일 Source가 여러 Target에 연결됐을 때 Source 평가 1회
- Shape Key Linker와 무관한 Object 변경 시 전체 Object 순회 없음
- Target Edit Mode 장기 유지 시 0.1초 polling 없음

### 오류와 복구

- evaluated mesh 정점 수 불일치
- Source 삭제 및 Undo 복구
- Shape Key 삭제, 삽입, Rename, Reorder 조합
- Link 삭제 직전에 예약된 dirty 항목 처리
- 파일 Load, Undo, Redo 후 reverse cache 재구축

### Cycle

- 직접 순환 `A → B → A`
- 간접 순환 `A → B → C → A`
- 순환이 없는 다중 Target 연결

### 호환성

- Blender 4.5.5 LTS
- Blender 5.0
- Blender 5.2 LTS
- Add-on register / unregister 반복
- `.blend` 저장 후 reload

## 배포 기준

각 Phase는 다음 조건을 만족한 뒤 배포한다.

- 기존 수동 Join, Update All, 개별 Update 동작 유지
- 기존 `.blend` 링크 데이터와 하위 호환
- Blender 4.5, 5.0, 5.2 자동 테스트 통과
- Extension ZIP build 및 validate 통과
- 한국어, 영어, 일본어 문서 동시 갱신
- 성능 개선은 호출 횟수 또는 처리 시간 측정 결과를 기록

## 구현 권장 순서 요약

1. Target Edit Mode timer polling 제거
2. Dirty Source/Link 단위 갱신
3. Source evaluated mesh 결과 공유
4. Reverse Lookup 및 캐시 수명 관리
5. Live Update 오류 상태 UI
6. 모호한 Shape Key 식별 차단
7. 선택적 Connectivity Validation
8. Live dependency cycle 검사
9. Source 선택/Frame 등 후속 UX
