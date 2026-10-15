# `@rig-c/parts` · `@rig-c/core` · `@rig-c/play` 실전 리깅 피드백 보고서

`family/jinni` (`800×2284`, 4x-AnimeSharp 업스케일 + Qwen-Image-Layered `1024×1024` 29레이어) 캐릭터를 리깅하고 실시간 물리 뷰어(`@rig-c/play`)에 탑재하면서 발견한 파이프라인의 구조적 병목과 개선 제안입니다.

---

## 1. `assemble.ts` — `projectSource()`와 `seamOverride()`가 전경 파츠 외곽을 배경 파츠에 스탬핑하는 문제

### 현상
- 치마(`bottomwear`) 위에 오른손(`handwear_r`)이 겹쳐 있거나, 목/쇄골(`neck`, `topwear`) 위에 앞머리 컬(`hair_front`)이 내려오는 구도에서, `rig-parts build`를 실행하면 **배경 파츠(`bottomwear`, `topwear`, `neck`) 텍스처에 전경 파츠(`handwear_r`, `hair_front`)의 검은 외곽선이나 픽셀이 그대로 찍혀 나오는(stamping) 현상**이 발생합니다.
- 그 결과 팔이나 머리카락이 물리로 조금만 움직여도 배경 파츠에 박힌 검은 잔상이 이중으로 드러납니다.

### 원인 분석 (`assemble.ts`)
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

## 2. `assemble.ts` — Lanczos3 레이어 업스케일 시 `[0, 0, 0, 0]` 경계 네거티브 로브 링잉(Ringing)과 `CORE_ERODE`의 결합 버그

### 현상
- `head:neck`과 `full:topwear`가 만나는 목 아래 이음매(`y ≈ 566..584`)에서 두 파츠의 `alpha` 합이 `255`로 완벽히 겹치는데도, 합성 결과(`recomposite.png` 및 뷰어)에 **가로로 2px 두께의 밝거나 어두운 실금(구멍처럼 보이는 줄)**이 나타났습니다.

### 원인 분석
1. 입력 레이어(`1024×1024`)에서 파츠 외곽 바깥(`alpha == 0`) 픽셀의 RGB가 `[0, 0, 0]`(검정)으로 비어 있을 때, `assemble.ts`가 이를 `2284×2284`로 **Lanczos3 보간 업스케일**합니다.
2. Lanczos3 커널의 네거티브 로브(negative lobe) 특성 때문에 `[0, 0, 0]`에서 피부색 `[215, 81, 93]`으로 급격히 뛰는 경계 안쪽 첫 2~3px 구간(`alpha >= 250`)에서 RGB가 `[230, 87, 100]`으로 오버슛(overshoot ringing)됩니다.
3. 이어서 실행되는 `projectSource()`는 `CORE_ERODE = 2px`만큼 안쪽만 원화(`painting.png`)로 덮어쓰기 때문에, **가장자리 2px 구간의 Lanczos3 오버슛 색상이 원화로 교정되지 못하고 그대로 아틀라스에 남게 됩니다.**

![Neck Seam & Ringing Fix](./jinni/docs/diag_neck_hole.png)

### 현재 우회법
- `scripts/upgrade_jinni_4x.py`에서 `full:topwear`의 `alpha == 0` 투명 영역(`ry = 272..283`)에도 인접한 피부 RGB 값을 미리 채워 넣어(RGB pre-fill / edge color bleeding) Lanczos3 업스케일 시 RGB 불연속이 발생하지 않도록 처리했습니다.

### 개선 제안
- `assemble.ts`에서 `1024×1024` 레이어를 캔버스 크기로 리사이즈하기 **직전**에, 모든 레이어에 대해 **Unpremultiplied RGB Edge Padding (투명 픽셀 `alpha == 0`에 최근접 불투명 픽셀의 RGB를 4~6px 확산)** 패스를 기본 적용하면 Lanczos3 링잉 아티팩트가 파이프라인 전역에서 사라집니다.

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

## 5. `@rig-c/core` — `contour.regions` 원형 리파인먼트 영역 간 오버랩 제약 완화 (`RIG_CONTOUR_REGIONS_OVERLAP`)

### 현상
- `topwear` 메시에 양쪽 가슴 지글 본(`boob_r`, `boob_l`)을 넣기 위해 `contour.regions`에 두 개의 원(`circle`) 영역을 정의할 때, `(r1 + band1) + (r2 + band2) > dist(center1, center2)`이면 `RIG_CONTOUR_REGIONS_OVERLAP` 에러로 빌드가 중단됩니다.
- 특히 3/4 뷰 캐릭터에서는 화면 우측 가슴이 실루엣 밖으로 크게 돌출되어 있어 `radius`와 `band`를 넉넉히 잡아야 끝단까지 자연스럽게 흔들리는데, 두 원의 `band`가 가슴골(cleavage) 중앙에서 조금만 닿아도 에러가 발생해 수 픽셀 단위로 반경을 깎아내야 했습니다 (`bust_r` 우측 끝 `442` vs `bust_l` 좌측 끝 `444`로 2px 간격을 수동 계산).

![Bust Contour Grid](./jinni/docs/diag_bust_grid.png)

### 개선 제안
- 인접한 두 `contour.regions`의 `radius`(코어 영역)끼리 겹치지 않고 외곽 감쇠 구간(`band`)만 겹치는 경우에는 에러를 던지는 대신, **두 영역의 거리 비율(Voronoi midpoint / smoothstep partition)로 가중치를 자동 정규화(normalize)**해주면 좌우 대칭/비대칭 트윈 리전(양쪽 가슴, 양쪽 볼, 양쪽 소매 끝 등) 설정이 훨씬 직관적해집니다.

---

## 6. `@rig-c/play` — `player.environment.wind` 타입 시그니처 및 `player.moved()` 임펄스 안정성

### 현상
1. `player.environment = { wind: 0 }`처럼 스칼라 숫자를 전달하면 런타임에 `the live track's setEnvironment's wind is 0, not a pair of finite numbers [x, y]` 예외가 발생합니다.
2. 마우스 드래그 이벤트를 `player.moved(dx, dy)`에 그대로 전달하면, 빠른 마우스 이동 시 단일 프레임 임펄스가 과도하게 들어가 물리 체인이 순간적으로 뒤집히거나 스톱 경계에서 떨리는 현상이 있습니다.

### 개선 제안
1. `setEnvironment({ wind })`에서 `typeof wind === 'number'`인 경우 내부적으로 `[wind, 0]`으로 자동 정규화(coercion)하거나, TypeScript 타입 정의와 README 예제에 `[x, y]` 튜플 형식을 명시적으로 강조하면 사용자 실수를 줄일 수 있습니다.
2. `player.moved(dx, dy)` 내부에 기본 최대 임펄스 클램프(예: `maxDelta = 20`) 옵션을 두면 별도의 뷰어 단 클램핑 없이도 안정적인 드래그 물리를 제공할 수 있습니다.

---

## 7. `rig-parts compose` — `rig.json.stops` 필드 미인식(`SCENE_BUILD_FIELD_KNOWN`) 버그

### 현상
- 각 캐릭터(`roa`, `jinni`)의 `config.json`에 물리 관통 방지용 `stops` (`RigStop`)를 선언하고 `rig-parts build`를 통과시킨 뒤, `rig-parts compose`로 두 캐릭터를 단일 씬으로 병합하면 다음 에러로 거부됩니다:
  ```text
  FAIL SCENE_BUILD_FIELD_KNOWN: character "roa" (../roa/out) rig.json.stops — is a key compose does not know how to prefix or place (it knows spec, name, images, skeleton, bones, slots, skins, constraints, invariants)
  ```

### 원인 분석
- `rig-parts build`(`src/rig.ts`)는 `config.stops`를 `out/rig/rig.json`의 최상위 `stops` 배열(`{ chain, links, against, at, inward, outward, lower }`)로 출력합니다.
- 반면 `src/compose.ts`의 허용 키 화이트리스트에는 `stops`가 누락되어 있어, `stops`를 사용한 모든 캐릭터 빌드가 `compose` 단계에서 차단됩니다.

### 개선 제안
- `src/compose.ts`에서 `rig.json.stops`를 허용 키에 추가하고, 각 `stop` 엔트리의 `chain`, `links[]`, `against` 본 이름에 `<id>:` 프리픽스를 붙여 합성된 `rig.json.stops`로 병합(및 `scale` 설정 시 `at: [x * s, y * s]` 스케일링)하도록 수정하면 `stops`가 적용된 캐릭터들도 즉시 `rig-parts compose`로 단일 스켈레톤 병합이 가능해집니다.

---

## 8. `@rig-c/core` / `rig-parts` — 가슴 지글의 입체감 부족 문제 및 2.5D 반구형 돔 디포머(`shape: "dome"`) 제안

### 현상
- 현재 `contour.regions`의 `shape: "circle"`은 반경 `r` 내부 정점들에 가중치 `1.0`을 균일하게 부여하고 `band` 구간에서만 선형 감쇠하는 **평면 원판(flat 2D disk)** 구조입니다.
- 이 상태에서 `boob_r`/`boob_l` 본에 `translatex`/`translatey`를 주면, 봉긋하게 솟아오른 3차원 구면이 출렁이는 것이 아니라 **평평한 원형 스티커(패치)가 옷 위에서 상하좌우로 미끄러지듯 평행 이동**하여 입체감이 전혀 느껴지지 않고 어색해 보입니다.
- 현재 리깅에서는 우회책으로 코어 반경 `r`을 유두/정점 부근(`16~18px`)으로 작게 줄이고 감쇠 구간 `band`를 넓게(`32~36px`) 잡은 뒤 진폭을 낮춰 평행 이동 느낌을 완화했으나, 근본적인 3D 볼륨감을 표현하기에는 한계가 있습니다.

### 개선 제안 (`@rig-c/core` 및 `rig-parts` 피처 제안)
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

### 현재 우회법 (`viewer/index.html`)
- 뷰어 로드 시 `assets.skeleton.animations`의 `idle` 타임라인에서 눈깜빡임 본(`eye_r`, `eye_l`, `lash_r`, `lash_l`, `iris_r`, `iris_l`)의 `scaleY` 키프레임을 분리해 별도의 원샷 `blink` 애니메이션 클립을 동적으로 생성하고, `idle`에서는 눈을 상시 뜬 상태로 유지시켰습니다.
- 이후 캐릭터별로 독립된 랜덤 타이머(`2.2s ~ 6.2s` 균등/지수 분포 + 18% 확률의 연속 더블 블링크)를 돌려 상위 애니메이션 트랙(또는 런타임 본 스케일 오버라이드)으로 비동기 재생하도록 구현했습니다.

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
- `assemble.ts`가 `--source`로 RGBA PNG를 직접 받을 수 있게 허용하고,
  1. 실루엣 판정은 RGB 색상 차이가 아닌 **원화 알파 채널(`source.alpha >= 128`)**을 기준으로 수행하며,
  2. `projectSource()`와 `seamOverride()`가 참조하는 원화 RGB는 `source.alpha >= 245`인 순수 불투명 내부 코어 픽셀들로부터 바깥쪽으로 4~6px 거리 변환 외삽(`distance_transform_edt` / unpremultiplied color decontamination)한 RGB를 사용하도록 개선하면, 어떤 배경색에서도 가장자리 흰 점 현상이 원천 차단됩니다.

