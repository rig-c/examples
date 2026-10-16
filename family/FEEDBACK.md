# `@rig-c/parts` · `@rig-c/core` · `@rig-c/play` 실전 리깅 피드백 보고서

`family/jinni` (`800×2284`, 4x-AnimeSharp 업스케일 + Qwen-Image-Layered `1024×1024` 29레이어) 캐릭터를 리깅하고 실시간 물리 뷰어(`@rig-c/play`)에 탑재하면서 발견한 파이프라인의 구조적 병목과 개선 제안입니다.

## 검증 상태 및 현행 코드 대조

아래 현상과 우회법은 이 데모 작성자의 작업 기록입니다. 원인 설명·개선 제안은 별도로 검증해야 하며, 저장된 `check.json`의 PASS가 실시간 물리·시각 인수를 대신하지 않습니다. 이 문서 정정에서는 새 설치·빌드·브라우저 재현을 실행하지 않았습니다. 출처가 없는 정밀 수치는 작성자 보고 또는 설정 목표로 보존하며 독립 실측값으로 주장하지 않습니다.

현행 계약 대조 기준은 parts [`bfdc4c4`](https://github.com/rig-c/parts/tree/bfdc4c443625b6eb4e214ccac93c7fd435670fe4), core [`89782d2`](https://github.com/rig-c/core/tree/89782d2ac6f43e9ddd7add248a92432626bd3757), play [`e234051`](https://github.com/rig-c/play/tree/e23405131a3bc43a9934dfe7131e62aee1b0bab2), 데모 원본 [`6142fcc`](https://github.com/rig-c/parts-examples/tree/6142fccf7b699fbd52b5351a6d9833645880bcbd)입니다. 데모의 정정 전 관찰과 당시 설명은 아래에 구분해 남깁니다.

후속 데모 교정과 원래의 upstream 가설은 별도입니다. 현재 승인된 다섯 authoring 입력의 정본·공식 재빌드 방법·SKIP는 [README의 현재 입력 절](./README.md#현재-승인된-입력과-재검증), 실제 수리와 기각한 방법은 [사례 기록](./REPAIR_CASE_STUDY.md)을 따릅니다. 이 문서의 초기 config 수치·dome/solver 제안·미검증 인과 설명을 현재 구현 완료나 새 core 계약으로 읽지 않습니다. 숨은 표면 수리와 뒷머리 생성은 각각 [Luna](./LUNA_HIDDEN_QUALITY.md), [Naru](./naru/BACKHAIR_REGENERATION.md)에 저작 출처를 남깁니다. [외형 원인 조사](./BUST_APPEARANCE.md)의 반응 차이·손 texel coupling 관찰도 원화 비대칭 전체가 결함이라는 판정과 구분합니다.

---

## 1. `assemble.ts` — `projectSource()`와 `seamOverride()`가 전경 파츠 외곽을 배경 파츠에 스탬핑하는 문제

### 현상
- 치마(`bottomwear`) 위에 오른손(`handwear_r`)이 겹쳐 있거나, 목/쇄골(`neck`, `topwear`) 위에 앞머리 컬(`hair_front`)이 내려오는 구도에서, `rig-parts build`를 실행하면 **배경 파츠(`bottomwear`, `topwear`, `neck`) 텍스처에 전경 파츠(`handwear_r`, `hair_front`)의 검은 외곽선이나 픽셀이 그대로 찍혀 나오는(stamping) 현상**이 발생합니다.
- 그 결과 팔이나 머리카락이 물리로 조금만 움직여도 배경 파츠에 박힌 검은 잔상이 이중으로 드러납니다.

### 초기 원인 분석 (`assemble.ts`, 재현 전 가설)

**정정:** `pixelOwners`의 `CORE_ALPHA = 250` 조건은 현행 코드에도 있지만, 이 설명만으로 전체 stamping 경로가 입증되지는 않습니다. 현행 [소유권 판정](https://github.com/rig-c/parts/blob/bfdc4c443625b6eb4e214ccac93c7fd435670fe4/src/assemble.ts#L615)과 [projectSource](https://github.com/rig-c/parts/blob/bfdc4c443625b6eb4e214ccac93c7fd435670fe4/src/assemble.ts#L673)는 rank·차폐·fringe 보호도 사용합니다. 아래는 작성 당시의 원인 가설이며, shield 없는 공개 입력으로 단계별 재현이 필요합니다. [#119](https://github.com/rig-c/parts/issues/119), [#255](https://github.com/rig-c/parts/issues/255)의 기존 보호와 [#351](https://github.com/rig-c/parts/issues/351)의 관련 진단 범위를 함께 확인해야 합니다. 제안된 alpha 임계치·팽창 폭은 아직 제품 계약이 아닙니다.

1. `projectSource()`에서 각 픽셀의 소유자(`pixelOwners`)를 판정할 때 `alpha >= CORE_ALPHA (250)`인 픽셀만 코어로 인정하고, 거기서 다시 `CORE_ERODE (2px)`만큼 침식(erosion)합니다.
2. 전경 파츠(`handwear-r`, `front hair`)의 가장자리 2~4px 구간이나 가는 머리카락 가닥은 `alpha`가 `180~248` 사이이거나 `CORE_ERODE`에 의해 전경 소유권을 잃습니다.
3. 이때 아래에 깔린 배경 파츠(`bottomwear`, `topwear`)는 해당 위치에서 `alpha == 255`(Qwen이 인페인팅으로 채워 넣은 온전한 배경 영역)이므로, **`pixelOwners`가 전경이 아닌 배경 파츠를 그 픽셀의 주인으로 판정**해 버립니다.
4. 결국 `projectSource()`가 4x 원화(`painting.png`)의 전경 픽셀(검은 장갑/소매, 짙은 갈색 머리카락)을 배경 파츠(`bottomwear`, `topwear`)에 그대로 복사해 넣게 되어, Qwen이 애써 복원해 둔 뒷배경 인페인팅이 파괴됩니다.

### 현재 우회법 (`scripts/upgrade_jinni_4x.py`)
- `layers.json`에서 배경 파츠보다는 위(`index`가 큼)이고 전경 파츠보다는 아래(`index`가 작음)에 있는 **미사용 레이어(`rank == -1`, 예: `12 full:neck`, `26 full:front hair`)에 전경 마스크(`alpha = 255`)를 인위적으로 주입**하여 `projectSource()`의 차폐 실드(shield)로 사용했습니다.

### 개선 제안

1. **전경 차폐 마스크(Foreground Occlusion Shield) 자동 생성**:
   - 특정 레이어 `L_bg`에 `projectSource()`를 수행할 때, `layers.json`에서 `L_bg`보다 상위(`z-order`가 앞)에 있는 모든 활성 파츠의 `alpha >= 16` (또는 `dilate(alpha >= 128, 2px)`) 영역에서는 **`painting.png` 픽셀 투영을 금지**하고, Qwen 레이어(`L_bg`) 고유의 인페인팅 RGB를 유지해야 합니다.
2. **`seamOverride()`의 Z-Order 방향성 제한**:
   - `seamOverride()` 역시 상위 파츠의 외곽 색상을 하위(가려진) 파츠의 내부로 번지게 해서는 안 되며, 동일 평면 인접 이음매(`neck` ↔ `topwear`, `thigh` ↔ `shin`)에만 작동하거나 하위 파츠가 상위 파츠 아래로 들어갈 때는 하위 파츠 자신의 내부 색상을 외삽(inward color extrapolation)하도록 개선하는 것이 안전합니다.

---

## 2. `assemble.ts` — 레이어 업스케일 이음매 관찰과 Lanczos3 / `CORE_ERODE` 원인 가설

### 현상
- `head:neck`과 `full:topwear`가 만나는 목 아래 이음매(`y ≈ 566..584`)에서 두 파츠의 `alpha` 합이 `255`로 완벽히 겹치는데도, 합성 결과(`recomposite.png` 및 뷰어)에 **가로로 2px 두께의 밝거나 어두운 실금(구멍처럼 보이는 줄)**이 나타났습니다.

### 초기 원인 분석 (미확정)

**정정:** 현행 RGBA Lanczos3는 [premultiply → resample → unpremultiply](https://github.com/rig-c/parts/blob/bfdc4c443625b6eb4e214ccac93c7fd435670fe4/src/raster/resize.ts#L251)를 수행합니다. 따라서 `alpha == 0` 픽셀의 검정 RGB가 그대로 색 보간에 섞인다는 아래 설명은 현행 구현의 확정 원인으로 사용할 수 없습니다. 같은 alpha·가시 RGB를 유지하고 alpha0 RGB만 바꾸는 대조, resize 직후와 투영 직후의 픽셀 비교가 필요합니다. 관찰된 실금과 당시 수정은 보존하되, 이 대조 없이 RGB prefill의 인과 효과나 전역 해결을 주장하지 않습니다.

1. 입력 레이어(`1024×1024`)에서 파츠 외곽 바깥(`alpha == 0`) 픽셀의 RGB가 `[0, 0, 0]`(검정)으로 비어 있을 때, `assemble.ts`가 이를 `2284×2284`로 **Lanczos3 보간 업스케일**합니다.
2. Lanczos3 커널의 네거티브 로브(negative lobe) 특성 때문에 `[0, 0, 0]`에서 피부색 `[215, 81, 93]`으로 급격히 뛰는 경계 안쪽 첫 2~3px 구간(`alpha >= 250`)에서 RGB가 `[230, 87, 100]`으로 오버슛(overshoot ringing)됩니다.
3. 이어서 실행되는 `projectSource()`는 `CORE_ERODE = 2px`만큼 안쪽만 원화(`painting.png`)로 덮어쓰기 때문에, **가장자리 2px 구간의 Lanczos3 오버슛 색상이 원화로 교정되지 못하고 그대로 아틀라스에 남게 됩니다.**

![Neck Seam & Ringing Fix](./jinni/docs/diag_neck_hole.png)

### 현재 우회법
- `scripts/upgrade_jinni_4x.py`에서 `full:topwear`의 `alpha == 0` 투명 영역(`ry = 272..283`)에도 인접한 피부 RGB 값을 미리 채워 넣어(RGB pre-fill / edge color bleeding) Lanczos3 업스케일 시 RGB 불연속이 발생하지 않도록 처리했습니다.

### 개선 제안
- `assemble.ts`에서 `1024×1024` 레이어를 캔버스 크기로 리사이즈하기 **직전**에, 모든 레이어에 대해 **Unpremultiplied RGB Edge Padding (투명 픽셀 `alpha == 0`에 최근접 불투명 픽셀의 RGB를 4~6px 확산)** 패스를 기본 적용하자는 초기 제안입니다. 전역 링잉 제거 효과는 검증되지 않았으며, premultiplied 경로에서의 효과와 정상 반투명 fringe 보존을 먼저 확인해야 합니다.

---

## 3. 고해상도(4x) 원화 + 저해상도(1024px) See-through/Qwen 레이어 하이브리드 지원

### 현상
- 실무에서는 생성된 원화를 `4x-AnimeSharp` 등으로 2000~4000px급으로 업스케일하여 아틀라스 선명도를 확보하지만, Qwen-Image-Layered / See-through 모델은 `1024×1024` 고정 해상도로 레이어를 출력합니다.
- 이때 `1024px` 레이어의 외곽 알파 마스크는 4x 원화의 날카로운 선화보다 2~4px 부풀어 있거나 거칠어서, 별도의 알파 정합 스크립트 없이는 외곽에 뿌연 헤일로(halo)나 톱니 노이즈가 남습니다.

### 개선 제안
- `rig-parts build`가 4x `painting.png`(RGBA)의 알파 채널 및 선화 그라디언트를 참조하여:
  1. 캐릭터 최외곽 실루엣과 맞닿는 파츠 경계는 `painting.png`의 고정밀 알파로 자동 클리핑(silhouette alpha clamping)하고,
  2. 가려진 하위 파츠 영역(Qwen이 인페인팅한 부분)은 `1024px` 레이어의 소프트 알파와 RGB를 보존하되, 노출된 코어 영역만 4x 원화를 투영하는 **`--upscaled-painting` (또는 자동 해상도 비율 감지) 모드**를 기본 지원하면 별도의 파이썬 후처리 없이도 즉시 4x 리깅이 가능해집니다.

---

## 4. `rig-parts propose` — 앞머리(`hair_front`)와 뒷머리(`hairback_*`) 본/텍스처 분리 및 기본 `stops` 제안

**현행 기능 정정:** 아래는 데모 작성 당시의 관찰입니다. [parts #364](https://github.com/rig-c/parts/issues/364)는 CLOSED이며 cloth/hair recipe와 leg stop 생성 작업이 착지했습니다. 따라서 “기본 stops가 없다”를 현행 전체 기능의 부재로 일반화하지 않습니다. 같은 입력·옵션으로 현재 `propose`가 생성하는 설정을 재현하고, 데모의 수작업 config와 비교해야 남은 실패를 판정할 수 있습니다. generator·강풍·체인 배치는 기존 [#378](https://github.com/rig-c/parts/issues/378), [#392](https://github.com/rig-c/parts/issues/392), [#390](https://github.com/rig-c/parts/issues/390)과 먼저 범위를 대조합니다. 이 문서 정정에서 해당 재현을 새로 실행하지는 않았습니다.

### 현상

1. `rig-parts propose`가 생성한 기본 설정에서 `meshes.hair_front.segments`에 `["head", "hairback_r", "hairback_l"]`이 모두 묶여 있고, `head:front hair` 레이어 하단(귀~어깨 옆)에 뒷머리 픽셀이 일부 포함되어 있었습니다.
2. 그 결과 뒷머리 물리(`hairback_r_phys`)가 작동할 때 **얼굴 옆 애교머리/앞머리까지 뒷머리 본에 끌려가며 목과 볼을 파고드는 현상**이 발생했습니다.
3. 또한 `hairback_*`과 `skirt_*` 체인에 기본 `stops` (`RigStop`)가 생성되지 않아, 바람(`wind`)이나 마우스 드래그 시 머리카락과 치마가 몸통 안쪽으로 과도하게 꺾여 살을 파고들었습니다.

### 개선 제안

1. **`hair_front` 세그먼트 분리**:
   - `hair_front` 메시는 기본적으로 `["head"]` (또는 이마/옆머리 전용 짧은 체인)에만 바인딩하고, 어깨 아래로 내려가는 `hairback_*` 체인은 `hair_back` 메시에만 바인딩하도록 `propose` 휴리스틱을 분리하는 것이 자연스럽습니다.
2. **물리 체인 기본 `stops` 자동 생성**:
   - `propose`가 `skirt_r/c/l` 및 `hairback_r/l` 체인을 생성할 때, 각각 `hip` 및 `chest`를 `against`로 하는 기본 각도 제한(`stops`, 예: 몸통 안쪽 방향 `8°~12°`, 바깥쪽 방향 `15°~20°`)을 함께 제안해주면 초기 빌드 직후의 물리 안정성이 크게 향상됩니다.

---

## 5. `@rig-c/parts` — `contour.regions` 원형 리파인먼트 영역 간 오버랩 제약 완화 (`RIG_CONTOUR_REGIONS_OVERLAP`)

### 현상

**정정:** 이 named refusal의 발행자는 core가 아니라 parts [src/rig.ts](https://github.com/rig-c/parts/blob/bfdc4c443625b6eb4e214ccac93c7fd435670fe4/src/rig.ts#L1483)입니다. 실제 판정은 메시 정점에 두 region의 가중치가 함께 걸리는지 읽습니다. 아래 원 반경 부등식은 작성 당시의 기하 설명이며 그 자체가 정확한 validator 조건은 아닙니다. 현행은 한 정점의 중복 falloff를 의도적으로 거부하므로, 자동 정규화는 새 opt-in 정책 연구로 구분합니다.

- `topwear` 메시에 양쪽 가슴 지글 본(`boob_r`, `boob_l`)을 넣기 위해 `contour.regions`에 두 개의 원(`circle`) 영역을 정의할 때, `(r1 + band1) + (r2 + band2) > dist(center1, center2)`이면 `RIG_CONTOUR_REGIONS_OVERLAP` 에러로 빌드가 중단됩니다.
- 특히 3/4 뷰 캐릭터에서는 화면 우측 가슴이 실루엣 밖으로 크게 돌출되어 있어 `radius`와 `band`를 넉넉히 잡아야 끝단까지 자연스럽게 흔들리는데, 두 원의 `band`가 가슴골(cleavage) 중앙에서 조금만 닿아도 에러가 발생해 수 픽셀 단위로 반경을 깎아내야 했습니다 (`bust_r` 우측 끝 `442` vs `bust_l` 좌측 끝 `444`로 2px 간격을 수동 계산).

![Bust Contour Grid](./jinni/docs/diag_bust_grid.png)

### 개선 제안
- 인접한 두 `contour.regions`의 `radius`(코어 영역)끼리 겹치지 않고 외곽 감쇠 구간(`band`)만 겹치는 경우에는 에러를 던지는 대신, **두 영역의 거리 비율(Voronoi midpoint / smoothstep partition)로 가중치를 자동 정규화(normalize)**해주면 좌우 대칭/비대칭 트윈 리전(양쪽 가슴, 양쪽 볼, 양쪽 소매 끝 등) 설정이 훨씬 직관적해집니다.

---

## 6. `@rig-c/play` — 환경·이동 API 호출 계약과 임펄스 관찰

### 당시 실패 호출 및 관찰

1. 초기 기록은 `player.environment = { wind: 0 }`에 `the live track's setEnvironment's wind is 0, not a pair of finite numbers [x, y]`라는 예외를 연결했습니다. 그러나 대입식은 실제 method 호출과 같지 않으므로, 이 호출식과 오류의 정확한 연결은 재현 전까지 확정하지 않습니다.
2. 초기 기록은 `player.moved(dx, dy)`로 드래그를 전달할 때 큰 임펄스에 체인이 뒤집히거나 stop 경계가 떨렸다고 기술했습니다. 이 두 인자 호출은 실제 API가 아니므로, 올바른 호출·좌표 단위로 다시 재현해야 엔진 결함과 입력 오용을 구분할 수 있습니다.

### 현행 계약 정정

[실제 공개 API](https://github.com/rig-c/play/blob/e23405131a3bc43a9934dfe7131e62aee1b0bab2/src/player.ts#L529)는 method와 객체 인자를 사용합니다:

```js
player.environment({ wind: [0, 0], gravity: [0, 1] });
player.moved({ x: deltaX, y: deltaY, rotation: deltaDegrees });
```

환경 `wind`/`gravity`는 유한한 `[x, y]` 쌍이며 y-down입니다. [`moved`](https://github.com/rig-c/play/blob/e23405131a3bc43a9934dfe7131e62aee1b0bab2/src/player.ts#L556)는 `{ x?, y?, rotation? }`를 받고 skeleton world 단위, y-up, 반시계 방향 degree를 사용합니다. page pixel delta는 consumer가 root scale로 나누고 y를 반전하여 전달합니다. `dx`/`dy` 필드나 두 positional 인자를 받는 계약이 아닙니다. [play #121](https://github.com/rig-c/play/issues/121)에 이 기능이 이미 구현되어 있습니다.

### 남은 검증 및 제안

기존 scalar 자동 변환과 기본 `maxDelta = 20` 클램프 제안은 도입 근거가 확인되지 않은 제안으로 보존합니다. 먼저 실제 객체 호출, root scale, 입력 속도·단위·시간 간격을 고정해 과도한 응답을 재현해야 합니다. 임의 클램프로 원인이나 stop 실패를 숨기지 않습니다.

---

## 7. `rig-parts compose` — `rig.json.stops` 필드 미인식(`SCENE_BUILD_FIELD_KNOWN`) 버그

### 현상
- 각 캐릭터(`roa`, `jinni`)의 `config.json`에 물리 관통 방지용 `stops` (`RigStop`)를 선언하고 `rig-parts build`를 통과시킨 뒤, `rig-parts compose`로 두 캐릭터를 단일 씬으로 병합하면 다음 에러로 거부됩니다:
  ```text
  FAIL SCENE_BUILD_FIELD_KNOWN: character "roa" (../roa/out) rig.json.stops — is a key compose does not know how to prefix or place (it knows spec, name, images, skeleton, bones, slots, skins, constraints, invariants)
  ```

### 원인 분석

**정정:** §12는 이 절과 같은 누락을 다시 기록한 것입니다. 이 절을 stop 병합 문제의 정본으로 삼으며, 후속은 [parts #431](https://github.com/rig-c/parts/issues/431)에서 추적합니다. 본문의 에러는 작성자 보고이며 이번 정정에서 CLI를 새로 실행하지 않았습니다. 원문의 `src/compose.ts` 지목은 `src/scene.ts`로 바로잡습니다.

**후속 상태:** #431은 [parts PR #434](https://github.com/rig-c/parts/pull/434), commit `bc5b73733bdf73c2cc9f45fbbac9f14eea51981a`에서 해결되어 닫혔습니다. 아래의 허용 키 누락 설명은 위에 고정한 과거 코드의 기록이며, 현재 미해결 결함으로 주장하지 않습니다.

- `rig-parts build`(`src/rig.ts`)는 `config.stops`를 `out/rig/rig.json`의 최상위 `stops` 배열(`{ chain, links, against, at, inward, outward, lower }`)로 출력합니다.
- 반면 실제 구현 파일인 [`src/scene.ts`의 허용 키 목록](https://github.com/rig-c/parts/blob/bfdc4c443625b6eb4e214ccac93c7fd435670fe4/src/scene.ts#L385)에는 `stops`가 누락되어 있어, `stops`를 사용한 모든 캐릭터 빌드가 `compose` 단계에서 차단됩니다.

### 개선 제안
- `src/scene.ts`에서 `rig.json.stops`를 허용 키에 추가하고, 각 `stop` 엔트리의 `chain` 이름과 `links[]`·`against` 본 참조에 `<id>:` 프리픽스를 붙여 합성된 `rig.json.stops`로 병합(및 `scale` 설정 시 `at: [x * s, y * s]` 스케일링)하는 경로가 필요합니다. 이것만으로 실행 인수가 끝나는 것은 아니며, 정상 gate와 실제 stop 동작 비교가 필요합니다.
- [실제 `RigStop` 타입](https://github.com/rig-c/core/blob/89782d2ac6f43e9ddd7add248a92432626bd3757/src/rig.ts#L1926)은 `chain`, `links`, `against`, `at`, `inward`, `outward`, `lower?`입니다. `chain`은 생성할 stop 객체들의 이름 기준이며 `links`/`against`는 본 참조입니다. `at`은 `against`의 **로컬 좌표**이므로 scene 이동 offset을 더하지 않습니다. 실제 namespace는 `<id>:`이며 `bone`/`parent` 또는 `<id>_`가 아닙니다.
- 두 멤버의 같은 로컬 이름, 허용된 scale·배치, 실제 physics-on 응답을 대조하고, 잘못된 참조의 named refusal과 stop 없는 기존 결과를 유지해야 합니다. 현행 force/scale 거부나 검증 gate를 완화해서는 안 됩니다.

---

## 8. `@rig-c/core` / `rig-parts` — 가슴 지글의 입체감 부족 문제 및 2.5D 반구형 돔 디포머(`shape: "dome"`) 제안

### 현상
- 현재 `contour.regions`의 `shape: "circle"`은 반경 `r` 내부 정점들에 가중치 `1.0`을 균일하게 부여하고 `band` 구간에서만 선형 감쇠하는 **평면 원판(flat 2D disk)** 구조입니다.
- 이 상태에서 `boob_r`/`boob_l` 본에 `translatex`/`translatey`를 주면, 봉긋하게 솟아오른 3차원 구면이 출렁이는 것이 아니라 **평평한 원형 스티커(패치)가 옷 위에서 상하좌우로 미끄러지듯 평행 이동**하여 입체감이 전혀 느껴지지 않고 어색해 보입니다.
- 현재 리깅에서는 우회책으로 코어 반경 `r`을 유두/정점 부근(`16~18px`)으로 작게 줄이고 감쇠 구간 `band`를 넓게(`32~36px`) 잡은 뒤 진폭을 낮춰 평행 이동 느낌을 완화했으나, 근본적인 3D 볼륨감을 표현하기에는 한계가 있습니다.

### 개선 제안 (`@rig-c/core` 및 `rig-parts` 연구 제안)

**검증 범위:** 아래 profile·scale 결합은 표현 연구 제안입니다. 실제 3D 체적 보존이나 특정 상용 도구와의 동등성을 검증하지 않았습니다. [core #382](https://github.com/rig-c/core/issues/382)의 기존 depth/bind/parallax 기능과 [#381](https://github.com/rig-c/core/issues/381)의 density/fold 측정을 먼저 비교해야 합니다.

**기존 기능과의 관계:** CLOSED인 #382는 depth-map sampling과 bind/parallax의 기존 구성 요소를 제공합니다. 이는 아래에서 제안한 `shape: "dome"` falloff나 자동 squash/stretch가 이미 구현되었다는 뜻은 아닙니다. #381의 density 연구는 dome의 fold 한계가 정점 수만으로 해결되지 않음을 다루므로, 기존 primitive로 같은 입력·가동 범위의 apex/지지부 변위와 fold를 비교한 뒤 추가 기능의 필요성을 판단해야 합니다. 두 카드의 착지를 실제 원화의 3D 체적 보존 또는 새 solver의 인수로 대신하지 않습니다.


1. **2.5D 반구형 돔 가중치 프로필 (`shape: "dome"` 또는 `profile: "cosine-dome"`)**:
   - 원판 전체에 `w = 1.0`을 주는 대신, 중심 정점(apex, $(c_x, c_y)$)에서의 정규화 거리 $d = \sqrt{((x - c_x)/r_x)^2 + ((y - c_y)/r_y)^2} \in [0, 1]$에 대해 반구형 고도 함수
     $$w(d) = \cos\left(\frac{\pi}{2} d\right) \quad \text{또는} \quad \sqrt{1 - d^2}$$
     로 가중치를 부여하고, 중심에 동심원 정점 링(concentric rings, 2~3겹)을 자동 생성합니다.
   - 이렇게 하면 중심 정점(apex)이 가장 크게 움직이고 기저부(흉곽 경계)로 갈수록 곡률을 그리며 변위량이 감소하여, 2D 메시만으로도 봉긋하게 솟아오른 반구체가 회전·출렁이는 입체 착시(2.5D parallax)가 만들어집니다.
2. **수직 이동(`translatey`)에 연동된 자동 Squash & Stretch / Scale 커플링**:
   - 실제 입체 볼륨이 아래로 출렁일 때(`dy > 0`)는 하단 윤곽이 부풀면서 좌우 폭이 미세하게 퍼지고(`scalex > 1, scaley < 1`), 위로 솟구칠 때(`dy < 0`)는 위아래로 봉긋해지는(`scaley > 1`) **체적 보존(volume-preserving squash & stretch)** 커플링 옵션을 `physics` 또는 `contour.regions`에 지원하면 단 1개의 지글 본으로도 Live2D/Spine Pro 수준의 입체적인 바스트 모션을 자동 생성할 수 있습니다.
3. **비대칭 타원 및 하단 언더바스트 고정(`anchor_arc`) 옵션**:
   - 가슴 상단(윗가슴/쇄골 쪽)은 완만하게 늘어나고 하단(밑가슴 주름, inframammary fold)은 흉곽에 단단히 받쳐지도록 상·하단 감쇠 반경(`band_top`, `band_bottom`)을 비대칭으로 지정할 수 있는 파라미터를 제안합니다.

---

## 9. `motion.ts` / `@rig-c/play` — 다중 캐릭터 동시 재생 시 눈깜빡임 동기화 문제 및 비주기 랜덤 `blink` 트랙 분리 제안

### 현상
- `rig-parts build`가 생성하는 `idle` 애니메이션은 고정 길이(`duration = 3.333s`) 루프 내부의 단일 시각(`blink.t`, 기본 `2.3s`)에 눈깜빡임 키프레임을 베이크(bake)합니다.
- 그 결과 한 화면에 여러 캐릭터(5인 합성 등)를 띄우면, 설령 각 캐릭터의 `blink.t`를 서로 다르게 오프셋하더라도 **모든 캐릭터가 정확히 `3.333초`마다 기계적으로 같은 주기로 눈을 깜빡여** 강한 이질감이 발생합니다.

### 현재 우회법 (`viewer/index.html`) — 구현 설명 정정

- 초기 문서는 로드 시 `idle` 키를 별도 one-shot `blink` 클립으로 분리했다고 기록했으나, [실제 viewer](https://github.com/rig-c/parts-examples/blob/6142fccf7b699fbd52b5351a6d9833645880bcbd/family/viewer/index.html#L239)는 `RigPlayer`의 `adjust(pose)`에서 `eye_r`/`eye_l`의 setup `scaleY`에 눈 감김 비율을 곱하고, 있는 경우 `brow_r`/`brow_l`의 setup y를 보정합니다. `assets.skeleton.animations`를 분리하는 구현은 아닙니다.
- [실제 타이머](https://github.com/rig-c/parts-examples/blob/6142fccf7b699fbd52b5351a6d9833645880bcbd/family/viewer/index.html#L186)는 초기 cooldown `0.5 + random × 2.8`초, 이후 `2.0 + random × 3.8`초, double blink 선택 확률 `20%`, 동작 길이 `0.21 + random × 0.06`초입니다. 원문의 `2.2~6.2초`, `18%`, 지수 분포 설명을 이 코드 기준으로 정정합니다. 이 값은 설정값이며 실제 시간 분포를 측정한 결과는 아닙니다.
- [play #87](https://github.com/rig-c/play/issues/87), [#93](https://github.com/rig-c/play/issues/93)의 다중 track/one-shot 기능은 이미 있습니다. 아래 별도 clip 출력은 parts의 선택적 기능 제안이며, 랜덤 재생 시점은 consumer가 정하는 scene 정책으로 구분합니다.

### 개선 제안

1. **`idle` 루프와 `blink` 애니메이션 클립의 기본 분리 (`animations: ["idle", "blink"]`)**:
   - `rig-parts`가 `skeleton.json`을 출력할 때 호흡/머리카락 흔들림만 담은 순수 루프 클립 `idle`과, `0.18s~0.22s` 길이의 짧은 원샷 클립 `blink`를 별도 애니메이션으로 분리해 출력하는 옵션(`blink.mode: "separate" | "baked"`)을 제안합니다.
2. **`@rig-c/play`의 내장 랜덤 블링크 스케줄러 (`autoBlink: { minInterval: 2.0, maxInterval: 6.0, doubleChance: 0.15 }`)**:
   - `@rig-c/play`의 `RigPlayer`가 Track 0에서 `idle`을 루프 재생하면서, `blink` 애니메이션이 존재할 경우 Track 1에서 자동으로 포아송/랜덤 간격으로 `blink`를 트리거해 주면 다중 캐릭터 씬에서도 별도의 커스텀 코드 없이 생동감 있는 눈깜빡임이 구현됩니다.

---

## 10. `assemble.ts` (`--seam silhouette`) — 흰색 배경 알파 합성 `painting.png` 사용 시 어두운 의상 가장자리 흰 점(White Dots) 스탬핑 문제

### 현상
- 검은색/남색 치마나 재킷(`luna`, `naru`, `nova`)처럼 어두운 의상이 배경과 맞닿는 외곽선에서, `rig-parts build --seam silhouette`를 실행하면 파츠 가장자리에 **오려내기가 잘못된 것 같은 하얀 점(white dots / light-grey edge speckles)**들이 다수 관찰됩니다.

### 원인 분석

1. 원본 RGBA 원화(`painting_rgba.png`)를 흰색 배경 `(255, 255, 255)` 위에 일반 알파 합성(`alpha_composite`)하여 `painting.png`를 만들면, 어두운 의상 외곽의 반투명 안티앨리어싱 픽셀(`0 < alpha < 250`)들이 흰색과 섞여 밝은 회색(`RGB ≈ 130..235`)이 됩니다.
2. `assemble.ts`의 `--seam silhouette` 규칙은 배경 테두리 색상(`[255, 255, 255]`)과의 차이가 `SILHOUETTE_LIMIT (40)`을 넘는 픽셀(즉 `min(R,G,B) < 215`)을 모두 인물 실루엣 내부로 판정합니다.
3. 그 결과 `growRim()`과 `seamOverride()`가 `painting.png` 가장자리의 흰색 섞인 밝은 회색 픽셀들을 "원화의 실제 색상"으로 오인하여 어두운 의상 파츠 가장자리에 불투명(`alpha = 255`)하게 찍어버립니다.

### 개선 제안
- **계약 정정:** 현행 [`sourceInRig`](https://github.com/rig-c/parts/blob/bfdc4c443625b6eb4e214ccac93c7fd435670fe4/src/assemble.ts#L554)는 읽은 source의 alpha를 `255`로 바꿉니다. 따라서 PNG 입력 허용 자체와 source alpha를 silhouette/투영에 사용하는 정책을 구분해야 합니다. 아래는 alpha-aware 처리 제안이며 효과를 새로 재현하지 않았습니다.
- 원화 alpha를 보존·사용하는 경로를 검토하고,
  1. 실루엣 판정은 RGB 색상 차이가 아닌 **원화 알파 채널(`source.alpha >= 128`)**을 기준으로 수행하며,
  2. `projectSource()`와 `seamOverride()`가 참조하는 원화 RGB는 `source.alpha >= 245`인 순수 불투명 내부 코어 픽셀들로부터 바깥쪽으로 4~6px 거리 변환 외삽(`distance_transform_edt` / unpremultiplied color decontamination)한 RGB를 사용하도록 개선하자는 제안입니다. `128`/`245` 임계값과 `4~6px` 폭은 검증된 범용 계약이 아니며, 흰색·어두운 matte 대조 및 정상 반투명 fringe를 보존하는 회귀 검증이 필요합니다.

---

## 11. `@rig-c/play` / `rig-parts` — 가슴 지글의 무중력(Zero-G) 유영 현상 해결을 위한 **중력 가속 낙하 + 비선형 J-커브 탄성 텐션(Hyperelastic Tension)** 솔버 내장 제안

### 현상
- `rig-parts`가 기본 생성하는 단일 정현파(`sineTrack`, $y(t) = A\sin(\omega_0 t)$)와 Spine 4.3의 기본 선형 `PhysicsConstraint`만으로는 가슴(`boob_r`, `boob_l`) 등 연부조직(soft-body)이 **위·아래 대칭 가속도로 움직여 마치 우주(무중력)에 둥둥 떠 있는 것처럼 보이는 현상**이 발생합니다.
- 실제 중력 환경에서 나타나는 **① 호흡 정점 이후의 빠른 중력 자유낙하(Free-Fall Drop), ② 최저점(바닥)에서 피부·쿠퍼인대·브라컵의 인장 한계에 걸려 팽팽하게 튕겨 오르는 탄성 텐션 스냅(Elastic Snap Rebound), ③ 바닥 충격 시 위아래가 눌리고 좌우 볼륨이 부풀어 오르는 3D 부피 보존 변형(Volume-Preserving Squash & Stretch)**이 기본 플레이어와 모션 생성기만으로는 표현되지 않습니다.

### 작성 당시 원인 분석 (`motion.ts`, 번들 내부 물리 수식)

**정정:** `Do()`는 번들 축약 식별자이며 안정된 공개 API 이름이 아닙니다. 아래 수식·평형·감쇠 수치는 작성자의 분석이며 고정된 입력 time-series로 독립 검증하지 않았습니다. 기존 Spine 호환 물리를 임의로 바꾸는 근거로 삼지 않습니다.

1. **`boob_r`/`boob_l` 수동 `sineTrack`과 `PhysicsConstraint` 동시 사용 시 호흡 중 상시 흔들림 발생**:
   - `@rig-c/play`의 물리 업데이트 함수(`Do()`)는 매 프레임 본의 월드 위치 변화량 `(o.uy - p) * e.inertia`를 `o.yOffset`에 직접 누적합니다.
   - 부모 본 `chest`가 이미 호흡 트랙(`translatey`, `amp = 5.0`)으로 움직이는 상태에서 자식 본 `boob_r`/`boob_l`에 수동 정현파 트랙(`motion.tracks`)까지 중복 부여하고 `inertia > 1.5`를 주면, 느린 호흡 중에도 매 프레임 큰 변위가 `yOffset`에 주입되어 가슴이 쉬지 않고 출렁이는 부작용이 발생합니다.
2. **낮은 `strength` + 높은 `damping`(`> 0.92`) + 과도한 `gravity` 조합 시 물풍선 진동 및 과도한 처짐 발생**:
   - `@rig-c/play`에서 중력 가속 항은 `C = e.gravity * e.referenceScale` (`referenceScale = 100`)으로 스케일링되어 `o.yVelocity -= (C * d.gravity[1] + o.yOffset * e.strength) * stepM`으로 적분됩니다.
   - 따라서 정적 중력 평형점 이동량은 $y_{\text{eq}} = -\frac{100 \cdot \text{gravity} \cdot d.\text{gravity}[1]}{\text{strength}}$이 되며, 낮은 `strength`(`150 ~ 200`)에 높은 `gravity`(`1.5 ~ 2.2`) 및 외부 베이킹/보정을 중첩하면 평형점이 `25 ~ 35px` 아래로 끌려 내려가 과도하게 늘어지는 현상이 발생합니다.
   - 또한 `damping`은 1/60초 프레임당 속도 유지율(`Math.pow(e.damping, 60 * dt)`)이므로, `damping = 0.94 ~ 0.96`과 낮은 `strength`를 결합하면 감쇠비 $\zeta < 0.14$가 되어 충격 후 7~10회 이상 출렁이는 물풍선 현상이 나타납니다.

### 작성자 설정 및 미검증 응답 목표 (`config.json`)

**측정 정정:** 아래의 `0.45초`, bounce 횟수, `0.07~0.23px` 및 `3.0~5.2px`는 작성자 보고값입니다. 입력 stimulus·시간 간격·좌표 단위·raw trace를 확인하지 못했으므로 독립 실측값이나 acceptance bar로 사용하지 않습니다. 각 Tier 괄호의 응답 수치도 같은 범위입니다. 저장된 `check.json`은 이런 응답 trace를 측정하는 문서가 아니며, physics를 제외한 검사 결과를 이 수치의 증거로 사용할 수 없습니다.

외부 베이킹 스크립트나 뷰어 런타임 보정 코드를 모두 걷어내고, **순수 `rig-parts` + `@rig-c/play`의 `PhysicsConstraint`만으로 2~3회 바운스 후 제자리를 찾는 탱글탱글한 탄성**을 구현하기 위해 다음과 같이 설정했습니다:

1. **`motion.tracks`에서 `boob_r` / `boob_l` 수동 트랙 제거**:
   - `boob_r`/`boob_l`은 `chest`의 자식 본으로서 수동 키프레임 없이 오직 `boob_r_phys`/`boob_l_phys` 물리 제약(`PhysicsConstraint`)으로만 구동됩니다.
2. **고강성(`strength = 278 ~ 480`) + 적정 속도 유지율(`damping = 0.85 ~ 0.89`) + 절제된 `inertia`(`0.30 ~ 0.47`) & `gravity`(`0.08 ~ 0.14`)**:
   - 느린 호흡(`period = 3.33s`, $\omega \approx 1.88\text{ rad/s}$)에서는 높은 복원 강성(`strength`) 덕분에 진폭이 `0.07 ~ 0.23px`로 억제되어 호흡 중 불필요하게 계속 흔들리지 않습니다.
   - 반면 드래그나 `찰랑이기` 등 빠른 충격이 가해지면 `3.0 ~ 5.2px` 범위로 탄력 있게 반응한 뒤 **2~2.5회 바운스(`0.45초` 이내) 만에 수렴한다는 작성자 주장**을 기록했습니다(독립 실측 미확인):
     - **Tier 1 (`luna`, Light-Perky, `r=22`)**: `strength: 480, damping: 0.85, inertia: 0.30, mass: 0.85, gravity: 0.08` (2.5회 바운스, 호흡 변위 `0.07px`)
     - **Tier 2 (`nova`, Medium-Firm, `r=23`)**: `strength: 425, damping: 0.86, inertia: 0.33, mass: 0.98, gravity: 0.10` (2.5회 바운스, 호흡 변위 `0.10px`)
     - **Tier 3 (`naru`, Medium-Full, `r=24`)**: `strength: 375, damping: 0.87, inertia: 0.37, mass: 1.10, gravity: 0.11` (2.0회 바운스, 호흡 변위 `0.14px`)
     - **Tier 4 (`jinni`, Heavy-Glamour, `r=25`)**: `strength: 325, damping: 0.88, inertia: 0.41, mass: 1.24, gravity: 0.12` (2.0회 바운스, 호흡 변위 `0.18px`)
     - **Tier 5 (`roa`, Max-Glamour, `r=28`)**: `strength: 285, damping: 0.89, inertia: 0.45, mass: 1.35, gravity: 0.14` (1.5~2.0회 바운스, 호흡 변위 `0.23px`)

### 향후 `@rig-c/play` / `rig-parts` 연구 제안

기본 물리의 Spine runtime parity를 유지해야 합니다. 아래 비선형 복원력·필터는 현재 기본 solver의 버그 수리로 확정한 항목이 아니며, 별도 opt-in 모델 계약과 oracle·core 검토가 필요한 연구입니다. “어떤 충격에도” 동작한다는 보장은 아직 측정하지 않았습니다.

1. **`PhysicsConstraint`에 하드/소프트 변위 제한(`limit` / 비선형 J-커브 텐션) 옵션 추가**:
   - 선형 스프링(`strength * yOffset`)만으로는 큰 충격이나 높은 중력(`gravity`)에서 하단 변위가 선형 비례로 늘어납니다. 일정 변위 이상에서 복원력이 3차 비선형($k_3 \Delta y^3$)으로 급증하는 **하단 텐션 스토퍼(`maxOffset` 또는 `tensionCurve`)**를 `@rig-c/play`의 `Do()` 솔버에 지원하면, 어떤 강한 외부 충격에도 가슴이 배꼽 쪽으로 늘어지지 않고 탱글하게 튕겨 오릅니다.
2. **저주파 호흡 속도 필터링(High-Pass Inertia Filter)**:
   - 부모 본(`chest`)의 느린 호흡 이동($< 0.5\text{Hz}$)에는 `inertia`가 과민 반응하지 않고, 빠른 가속도 변화(임펄스/드래그/점프)에만 `inertia`가 전달되도록 고역통과(High-Pass) 또는 가속도 기반 임펄스 모드를 지원하면 더욱 자연스러운 정지 호흡과 강한 타격감을 동시에 얻을 수 있습니다.

---

## 12. `rig-parts compose` (`scene.ts`) — `stops` 필드 포함 빌드 병합 시 `SCENE_BUILD_FIELD_KNOWN: rig.json.stops` 에러 및 다중 인스턴스 레이어링 제안

### 현상
- 각 캐릭터의 `config.json`에 각도 제한(`stops`)을 선언하여 빌드한 뒤, `rig-parts compose --scene scene.json --out composed_out`을 실행하면 다음과 같은 스키마 검증 에러로 중단됩니다:
  ```text
  SCENE_BUILD_FIELD_KNOWN: roa/out/rig.json.stops — unknown field "stops" in roa/out/rig.json (rebuild with current rigc?)
  ```

### §7과 동일한 결함 — 중복 및 계약 정정

이 stop 병합 문제의 정본은 **§7**입니다. 위 에러 문구는 작성자의 두 번째 기록이며 동일 CLI 실행의 raw log로 확인한 별도 재현은 아닙니다. `RIG_KEYS`는 `new Set(...)`이 아니라 배열이며, 실제 prefix는 `<id>:`입니다. 초기 문서의 `<memberId>_`, stop의 `bone`/`parent` 필드 설명은 실제 계약과 달라 정정합니다. `chain`·`links[]`·`against`와 against-local `at`의 처리 및 gate 조건은 §7을 따릅니다.

### 별도 소비자 편의 제안 (미검증)

1. **다중 캐릭터 합체 시 단일 스켈레톤 병합보다 `@rig-c/play`의 다중 레이어 스테이지(`offsetX`, `zIndex`, `phaseOffset`) 지원 권장**:
   - 5인 그룹처럼 캐릭터들이 어깨동무를 하거나 앞뒤로 포개어지는 구도에서는, 단일 거대 아틀라스/스켈레톤으로 합치는 것보다 개별 `RigPlayer` 인스턴스를 `offsetX`와 `z-index` 깊이 레이어링으로 배치하는 방식이 **캐릭터별 독립 랜덤 블링크, 호흡 위상차(`phaseOffset`), 앞뒤 깊이 정렬(`roa z=3` → `luna z=2` 어깨동무 등), 개별 아틀라스 캐싱 면에서 유연했다고 작성자가 평가했습니다**. 단일 합성과의 실행 시간·메모리·시각 비교는 수행하지 않아 효율 우위로 일반화하지 않습니다.
   - `@rig-c/play`에서 여러 캐릭터를 한 스테이지에 배치하고 환경(`wind`, `gravity`)과 드래그 임펄스(`moved`)를 일괄 브로드캐스트해 주는 경량 래퍼(` createStage({ members: [{ src, offsetX, offsetY, zIndex, phaseOffset }] }) `)를 기본 제공하면 다중 캐릭터 씬 구성이 더욱 간편해집니다.
