# Family — 5인 그룹 일러스트 업스케일 & 멀티 캐릭터 Spine 리깅 데모

`family/`는 한 장의 와이드 그룹 일러스트(`1024×571` RGBA)를 `4x-AnimeSharp`로 고해상도(`4096×2284`) 업스케일한 뒤, 5명의 캐릭터(`luna`, `roa`, `jinni`, `nova`, `naru`)를 개별 분리하여 [`@rig-c/parts`](https://github.com/rig-c/parts)(`rig-parts`) + [`@rig-c/core`](https://github.com/rig-c/core)(`rigc`)로 리깅하고 [`@rig-c/play`](https://github.com/rig-c/play)로 실시간 물리·합성 데모를 구동하는 실전 예제입니다.

첫 번째 완주 캐릭터인 **#3 Jinni (`jinni`, `800×2284`)**를 제작하면서 겪은 **저해상도(1024px) 레이어 분해 결과물과 4x 업스케일 원화 간의 정합 문제, `projectSource` 전경 스탬핑, Lanczos3 경계 링잉, 물리 관통 제어, 3/4 뷰 가슴 지글 리깅**의 전체 해결 과정과 재현 스크립트를 포함하고 있습니다.

> 파이프라인(`@rig-c/parts` / `@rig-c/core` / `@rig-c/play`) 개선을 위한 상세 기술 제안은 [FEEDBACK.md](./FEEDBACK.md)에 별도로 정리되어 있습니다.

---

## 디렉토리 구조 (Layout)

```text
family/
├── README.md                                 # 본 문서 (워크플로, 삽질 과정, 스크립트 및 데모 안내)
├── FEEDBACK.md                               # @rig-c/parts · @rig-c/core · @rig-c/play 기술 피드백 문서
├── group_1024x571_rgba.png                   # 원본 5인 와이드 투명 배경 일러스트 (1024×571 RGBA)
├── group_2048x1142_rgba.png                  # 2x Lanczos 업스케일 중간본 (2048×1142 RGBA)
├── group_2048x1142_animesharp_rgba.png       # 2x AnimeSharp 다운샘플 비교본 (2048×1142 RGBA)
├── group_4096x2284_animesharp_rgba.png       # 최종 4x-AnimeSharp 업스케일 그룹 원화 (4096×2284 RGBA)
├── scripts/
│   ├── upgrade_roa_4x.py                     # #1 Roa 4x 레이어 정제 & config 생성 스크립트
│   ├── upgrade_luna_4x.py                    # #2 Luna 4x 레이어 정제 & config 생성 스크립트
│   ├── upgrade_jinni_4x.py                   # #3 Jinni 4x 레이어 정제 & config 생성 스크립트
│   ├── upgrade_naru_4x.py                    # #4 Naru 4x 레이어 정제 & config 생성 스크립트
│   └── upgrade_nova_4x.py                    # #5 Nova 4x 레이어 정제 & config 생성 스크립트
├── viewer/
│   ├── index.html                            # @rig-c/play 기반 인터랙티브 Spine WebGL + 5인 동시 물리 데모 뷰어
│   └── server.mjs                            # 로컬 확인용 정적 파일 서버 (기본 포트: 4568)
└── roa/ luna/ jinni/ naru/ nova/             # 5인 전원 (각 800×2284, 전원 check PASS 완료)
    ├── config.json                           # 4x 해상도(800×2284) 최종 rig-parts 설정 (물리·stops·가슴 지글 포함)
    ├── inputs/
    │   ├── painting.png                      # 4x 크롭 원화 (800×2284 RGB, 흰색 매트)
    │   ├── painting_rgba.png                 # 4x 크롭 원화 (800×2284 RGBA)
    │   └── layers/
    │       ├── full_orig/                    # Qwen-Image-Layered 원본 전신 분해 결과 (1024×1024)
    │       ├── head_orig/                    # Qwen-Image-Layered 원본 헤드 분해 결과 (1024×1024)
    │       ├── full/                         # upgrade_*_4x.py가 정제·재구축한 전신 레이어 세트
    │       └── head/                         # upgrade_*_4x.py가 정제·재구축한 헤드 레이어 세트
    ├── out/                                  # rig-parts build 최종 산출물 (skeleton.json, skeleton.atlas, skeleton.png, idle.gif)
    └── docs/                                 # 정지 재합성(recomposite.png), 컨택트 시트(contact.png), 히트맵(motion_heat.png)
```

---

## 1. 입력 그림 및 4x 업스케일 파이프라인

### 1.1 원본 그룹 이미지와 4x-AnimeSharp 업스케일
- **원본 (`group_1024x571_rgba.png`)**: 5명의 캐릭터가 나란히 서 있는 `1024×571` RGBA 이미지입니다. 개별 캐릭터의 폭이 약 `200px`에 불과해, 그대로 리깅하면 눈매·머리카락 결·손가락 디테일이 뭉개집니다.
- **4x 업스케일 (`group_4096x2284_animesharp_rgba.png`)**:
  - ComfyUI의 `4x-AnimeSharp.pth` 모델로 RGB 채널(검정 배경 매트)과 알파 마스크(3채널 그레이스케일 변환)를 각각 `4096×2284`로 업스케일하여 외곽선 수축률이 정확히 일치하도록 결합했습니다 (`alpha < 8` 미세 노이즈 클리핑).
  - **#3 Jinni 크롭 영역**: 1x 기준 `x = 408..608` (`200×571`) → 4x 기준 `x = 1632..2432` (`800×2284`)를 잘라 [`jinni/inputs/painting.png`](./jinni/inputs/painting.png)로 사용합니다.

![Upscale Comparison](./jinni/docs/upscale_compare.png)

### 1.2 Qwen-Image-Layered (`1024×1024`) 입력 보존
- 레이어 분해 모델(`Qwen-Image-Layered`)은 고정 해상도(`1024×1024`)에서 동작하므로, 최초 분해 결과는 [`jinni/inputs/layers/full_orig/`](./jinni/inputs/layers/full_orig/) 및 [`jinni/inputs/layers/head_orig/`](./jinni/inputs/layers/head_orig/)에 원본 그대로 보존되어 있습니다.
- [`scripts/upgrade_jinni_4x.py`](./scripts/upgrade_jinni_4x.py)가 이 `full_orig` / `head_orig`의 의미론적(semantic) 파츠 마스크와 인페인팅(가려진 뒷배경 복원) 정보를 읽어, 4x 원화(`800×2284`)의 칼같은 선화 및 알파 경계에 맞춰 [`jinni/inputs/layers/full/`](./jinni/inputs/layers/full/)과 [`jinni/inputs/layers/head/`](./jinni/inputs/layers/head/)를 재구축합니다.

---

## 2. 리깅 설정 (`jinni/config.json`)

[`jinni/config.json`](./jinni/config.json)은 `800×2284` 캔버스 기준의 `rig-parts` 선언적 설정 파일입니다.

- **22개 파츠 (`parts`)**:
  - `head` 런에서 추출: `hair_back`, `ear_r`, `ear_l`, `neck`, `face`, `eye_r`, `eye_l`, `brow_r`, `brow_l`, `mouth`, `hair_front`
  - `full` 런에서 추출: `thigh_r`, `thigh_l`, `shin_r`, `shin_l`, `shoe_r`, `shoe_l`, `bottomwear`, `topwear`, `arm_r`, `arm_l`, `handwear_r`, `handwear_l`
- **스켈레톤 (`skeleton.points` & `chains`)**:
  - 중심 축: `hip` `[432, 1080]` → `waist` `[436, 868]` → `chest` `[442, 708]` → `neck` `[448, 560]` → `head` `[450, 480]` → `head_end` `[450, 210]`
  - 뒷머리 체인: `hairback_r` (3세그먼트), `hairback_l` (3세그먼트)
  - 치마 체인: `skirt_r`, `skirt_c`, `skirt_l` (각 2세그먼트)
  - **가슴 지글 본**: `chest` 하위에 좌우 독립 본 `boob_r` (`[384, 724]` → `[380, 756]`), `boob_l` (`[514, 720]` → `[518, 752]`) 배치
- **메시 (`meshes`)**:
  - `topwear`: `contour` 모드 + 좌우 가슴 원형 리파인먼트 영역(`bust_r`: `cx=384, cy=724, r=38, band=20`, `bust_l`: `cx=514, cy=720, r=46, band=24`)을 정의하여 몸통 외곽과 쇄골은 `chest`/`waist`에 고정하고 양쪽 가슴 볼륨만 독립적으로 탄성 변형되도록 구성
  - `hair_front`: 앞머리가 뒷머리 본에 끌려가지 않도록 `["head", "hairback_l"]`만 연결
- **물리(`physics`) & 각도 스톱(`stops`)**:
  - `hairback_r/l` (`chest` 기준 ±12°~18° 제한), `skirt_r/c/l` (`hip` 기준 ±8°~12° 제한)에 `stops`를 걸어 바람이나 드래그 시 치마가 허벅지를 파고들거나 머리카락이 어깨 살을 파고드는 현상 방지
  - `boob_r_phys`, `boob_l_phys`: `translateX=0.35`, `translateY=0.65`, `strength=55`, `damping=0.58`로 호흡 및 좌우 회전 시 자연스러운 2D 지글 구현

---

## 3. `rig-parts build` / `rigc build` 결과 (`jinni/out/`)

빌드 명령:

```bash
python3 scripts/upgrade_jinni_4x.py
npx --prefix /path/to/rig-parts rig-parts build --config jinni/config.json --dir jinni/inputs --out jinni/out
```

### 검증 지표 (11/11 PASS)

| 항목 | 수치 | 기준 | 결과 |
| :--- | :--- | :--- | :--- |
| `check` | **11 / 11 bar passed** | 전체 통과 | **PASS** |
| `loop` | **max \|d\| = 0** (`bone=hip.r`) | `<= 0.01` | **PASS** |
| `recomposite` | `corr=0.922`, `seam=0.056`, `out=0.000` | 외곽 누출 0 | **PASS** |
| `contact` | 6 poses (`wind`, `breath`, `sway`, `turn`, `nod`, `tilt`), `worst_tear=0.052` | 찢어짐 없음 | **PASS** |

````carousel
![Idle Loop GIF](./jinni/out/idle.gif)
<!-- slide -->
![6-Pose Contact Sheet](./jinni/out/contact.png)
<!-- slide -->
![Motion Heatmap](./jinni/out/motion_heat.png)
<!-- slide -->
![Recomposite](./jinni/out/recomposite.png)
````

---

## 4. 삽질 과정과 해결 스크립트 (`scripts/upgrade_jinni_4x.py`)

저해상도(`1024×1024`) Qwen 레이어와 고해상도(`800×2284`) 4x 원화를 결합해 리깅하면서 발생한 **6가지 핵심 난제와 해결 기법**입니다. 모든 처리는 [`scripts/upgrade_jinni_4x.py`](./scripts/upgrade_jinni_4x.py)에 코드로 문서화되어 있으며 언제든 100% 재현됩니다.

### 삽질 1: 치마(`bottomwear`) 파츠에 오른손이 그대로 찍히는 문제
- **원인**:
  1. 1차 스크립트에서 4x 원화의 픽셀을 `bottomwear` 마스크 전체에 덮어씌우면서 치마 위에 겹쳐진 오른손(`handwear_r`) 픽셀까지 치마 레이어에 혼입됨.
  2. 설령 치마 레이어에서 손을 지우더라도, `rig-parts`의 `assemble.ts`가 실행하는 `projectSource()` 단계에서 `handwear-r`의 반투명 외곽(`alpha < 250`) 픽셀은 `pixelOwners` 코어로 인정받지 못해, 바로 아래에 깔린 불투명한 `bottomwear`(`alpha = 255`)가 원화의 검은 소매·손가락 테두리를 그대로 흡수(stamping)함.
- **해결**:
  - [`jinni/inputs/layers/full_orig/parts/bottomwear.png`](./jinni/inputs/layers/full_orig/parts/bottomwear.png)에 Qwen이 인페인팅해 둔 **손 아래의 핑크색 대각선 치마 주름**을 `hwr_arm_zone` 영역에 복원하고 경계를 가우시안 블렌딩(`sigma=3.5`) 처리.
  - `layers.json` 순서상 `10 bottomwear` 위, `17 handwear-r` 아래에 위치한 미사용 레이어 **`12 full:neck` (`rank == -1`)**에 팔/손 모양의 불투명 마스크(`alpha = 255`)를 씌워 **`projectSource` 차폐 실드(shield)**로 활용. 이로써 `17 handwear-r`는 4x 원화 투영을 정상적으로 받으면서 `10 bottomwear`에는 손이 단 1픽셀도 찍히지 않음.
  - 추가로 `handwear_r` 손가락 끝의 반투명 픽셀에서 배경 치마 색상을 역산 제거(color decontamination)하고, `handwear_l`에 남아 있던 몸통 잔여물(`rx < 246`)을 클리닝.

![Skirt & Hand Fix](./jinni/docs/diag_skirt_hand.png)

### 삽질 2: 왼쪽 어깨(캐릭터 기준 오른쪽 맨어깨) 노이즈 및 소매 틈새
- **원인**:
  - `head:neck`의 어깨선이 `ry=315`에서 끝나는데 `full:topwear`의 상단 경계선이 너무 낮게(`ry=320`) 잘려 있어, 검은색 오프숄더 소매(`full:handwear-r`, `ry=315.5` 시작)와 맨어깨 사이에 빈 틈과 핑크/검정 경계 노이즈가 발생.
- **해결**:
  - `full:topwear`의 맨어깨 곡선(`shoulder_ctrl_rx_tw` / `shoulder_ctrl_ry_tw`)을 `ry=318.0`까지 매끄럽게 연장하여, 오프숄더 소매(`ry=315.5`) 아래로 2.5px 깊이만큼 자연스럽게 말려 들어가도록(under-tuck) 설계.

### 삽질 3: 목선 타고 내려온 머리카락 밑 바디 파츠(`neck` ↔ `topwear`) 구멍 & Lanczos3 링잉
- **원인**:
  1. 캐릭터 왼쪽 목선을 따라 쇄골까지 내려오는 짙은 갈색 머리카락 컬(`x=482..502, y=540..625`)이 `head:front hair`에서 누락되어, 그 아래 `neck`과 `topwear`에 검은 얼룩으로 찍힘.
  2. `head:neck` 하단(`y=584`)과 `full:topwear` 상단(`y=566`)이 만나는 경계에서, `full:topwear`의 `alpha == 0` 영역이 `[0, 0, 0, 0]`(검정)으로 비어 있다 보니 `assemble.ts`가 `1024 → 2284`로 **Lanczos3 업스케일**할 때 네거티브 로브(negative lobe) 오버슛이 발생함. 그 결과 `alpha >= 250` 시작점 첫 2줄의 RGB가 `[215, 81, 93]` 대신 `[230, 87, 100]`으로 하얗게 뜨고, `projectSource`의 `CORE_ERODE = 2px` 때문에 이 2줄이 원화로 덮어써지지 않아 가로 실금(구멍처럼 보이는 밝은 줄)이 남음.
- **해결**:
  - 쇄골 위 머리카락 가닥과 끝단 컬(`upper_strand_h | lower_curl_h`)을 색상 언믹싱(`unmix_fg`)으로 `head:front hair`에 온전히 편입하고, 미사용 레이어 `26 full:front hair`를 실드로 세워 `full:topwear`에 검은 머리카락이 찍히지 않게 보호.
  - `head:neck`을 순수 목 폭(`[true_neck_left_x_h, true_neck_right_x_h]`) 안으로만 제한하면서 아래(`ry=292.0`)까지 충분히 내리고, `full:topwear` 목 베이스 상단을 핑크색 목 그림자 아래(`ry=283.0`)에 배치.
  - **핵심**: `full:topwear`의 `alpha == 0` 투명 영역(`ry = 272..283`)에도 인접한 피부 RGB 색상을 미리 채워 넣어(RGB pre-fill) Lanczos3 업스케일 시 경계 오버슛/링잉을 0으로 제거.

![Neck Hole & Hair Curl Fix](./jinni/docs/diag_neck_hole.png)

### 삽질 4: 치마와 뒷머리 물리 관통 (살을 파고드는 현상)
- **원인**:
  - `meshes.hair_front.segments`에 `hairback_r`가 포함되어 있어 뒷머리가 흔들릴 때 얼굴 옆 앞머리까지 함께 꺾이며 볼과 목을 침범함.
  - 또한 `head:front hair` 텍스처 좌하단(귀 아래 `head_ry > 362`)에 뒷머리 픽셀이 섞여 있었고, 물리 체인에 각도 제한(`stops`)이 없었음.
- **해결**:
  - `head:front hair` 좌하단의 뒷머리 영역을 `head:back hair`로 이관하고, `meshes.hair_front.segments`에서 `"hairback_r"`를 제거.
  - `config.json`에 `stops` (`skirt_r/c/l` vs `hip`, `hairback_r/l` vs `chest`)를 추가하고 스프링 `strength`/`damping`을 높여 역방향 관통을 원천 차단.
  - [`viewer/index.html`](./viewer/index.html)에서 드래그 시 전달되는 `player.moved(dx, dy)` 임펄스를 프레임당 `[-14, 14]px`로 클램핑.

### 삽질 5: 3/4 뷰 양쪽 가슴 지글(`boob_r`, `boob_l`)과 `RIG_CONTOUR_REGIONS_OVERLAP`
- **원인**:
  - 캐릭터가 3/4 각도로 서 있어 왼쪽 가슴(화면 우측, `x=500..558`)이 실루엣 밖으로 돌출되어 있음.
  - `meshes.topwear`에 두 개의 `contour.regions` 원(`bust_r`, `bust_l`)을 넣을 때 `(r1 + band1) + (r2 + band2)`가 두 원 중심 간 거리보다 크면 `rig-parts`가 `RIG_CONTOUR_REGIONS_OVERLAP` 에러를 발생시킴. 반대로 원을 작게 줄이면 화면 우측 돌출부(`x=540..558`)가 `band` 감쇠 구간에 걸려 가슴 끝단만 고정된 채 안쪽만 흔들리는 어색한 변형이 생김.
- **해결**:
  - 중심점과 반경을 비대칭으로 정밀 설계:
    - `bust_r` (화면 좌측 가슴): `center=[384, 724], radius=38, band=20` → 우측 끝 `384 + 58 = 442`
    - `bust_l` (화면 우측 돌출 가슴): `center=[514, 720], radius=46, band=24` → 좌측 끝 `514 - 70 = 444`, 우측 `weight=1.0` 구간 `514 + 46 = 560` (돌출 실루엣 `x=558` 완벽 포함)
  - 두 영역 사이에 정확히 `2px`의 안전 간격(`442` vs `444`)을 확보하여 오버랩 에러 없이 양쪽 가슴 전체가 부드럽게 2D 지글하도록 완성.

![Bust Contour Grid](./jinni/docs/diag_bust_grid.png)

---

## 5. 에이전트 패밀리 5인 전원(`roa`, `luna`, `jinni`, `naru`, `nova`) 리깅 요약

| 순번 | 캐릭터 | 4x 크롭 구간 (`x`) | `head_box` | 정제 스크립트 | `check` 결과 | 주요 리깅 및 피드백 반영 특징 |
| :---: | :--- | :---: | :---: | :--- | :---: | :--- |
| **#1** | **Roa (`roa`)** | `96..896` | `[120, 110, 560, 550]` | [`scripts/upgrade_roa_4x.py`](./scripts/upgrade_roa_4x.py) | **PASS (`10/10`)** | 웨이브 보브(`hair_back`) 내 얼굴/귀걸이/셔츠 칼라 분리, 골반~무릎(`hip`) 고정 + 무릎 아래 와이드 팬츠 하단 물리, 커피잔+오른손 단일 메시 |
| **#2** | **Luna (`luna`)** | `896..1696` | `[150, 270, 590, 710]` | [`scripts/upgrade_luna_4x.py`](./scripts/upgrade_luna_4x.py) | **PASS (`10/10`)** | 타이트 펜슬 스커트 물리 제거(`not_swinging: ["bottomwear"]`) + 재킷 하단 밑자락(`hem_r`, `hem_l`) 물리, 어두운 의상 외곽 흰 점(Halo) 제거 |
| **#3** | **Jinni (`jinni`)** | `1688..2488` | `[216, 152, 656, 592]` | [`scripts/upgrade_jinni_4x.py`](./scripts/upgrade_jinni_4x.py) | **PASS (`11/11`)** | 오프숄더 니트 언더턱, 레드 플리츠 스커트 오른손 스탬핑 차폐(`12 full:neck` 실드), 봉긋한 코어(`r=16..18`)+넓은 탄성 경사(`band=34..36`) 가슴 지글 |
| **#4** | **Naru (`naru`)** | `2496..3296` | `[160, 300, 600, 740]` | [`scripts/upgrade_naru_4x.py`](./scripts/upgrade_naru_4x.py) | **PASS (`10/10`)** | 좌상단 어깨 흰색 잡티 제거 및 갈색 머리끝 복원, 골반~무릎(`hip`) 고정 + 무릎 아래 스커트 밑단 물리, 스커트 외곽 흰 점(Halo) 제거 |
| **#5** | **Nova (`nova`)** | `3296..4096` | `[200, 230, 730, 760]` | [`scripts/upgrade_nova_4x.py`](./scripts/upgrade_nova_4x.py) | **PASS (`9/9`)** | 오렌지-레드 `hair_back` 내 몸통(블레이저/셔츠) 픽셀 완전 분리 및 인페인팅, 바지 물리 제거(`not_swinging`) + 블레이저 밑자락(`hem_r`, `hem_l`) 물리, 바지/소매 외곽 흰 점 제거 |

![Family 5 Characters Recomposite](./docs_family_5chars_recomposite.png)

---

## 6. 라이브 뷰어 및 5인 동시 합성 데모 (`viewer/`)

로컬 웹 서버를 띄워 브라우저에서 실시간 Spine WebGL 렌더링, 바람(`wind`), 마우스 드래그 물리 관성, **5인 전원 동시 합성**을 바로 테스트할 수 있습니다.

```bash
node viewer/server.mjs
# Listening on http://localhost:4568
```

브라우저에서 `http://localhost:4568`을 열면 다음 기능을 사용할 수 있습니다:
- **캐릭터 및 합성 전환 (`#charSelect`)**:
  - **`합성 · 에이전트 패밀리 전원 (5인 동시)`**: 5명 전원(`roa`, `luna`, `jinni`, `naru`, `nova`)의 Spine WebGL 플레이어를 원본 그룹 일러스트의 정확한 4x 오프셋(`0, 800, 1592, 2400, 3200`)으로 단일 스테이지에 배치하고 바람·중력·드래그 관성을 실시간 동기화하여 구동
  - **비동기 독립 랜덤 눈 깜빡임**: `@rig-c/play`의 `adjust(pose)` 훅을 활용해 `idle` 루프에 구워진 주기적 블링크 대신 캐릭터별 독립 비주기 랜덤 타이머(`2.0~5.8s` 간격, 20% 확률 더블 블링크)와 호흡 위상 오프셋을 적용
  - `1번 · 로아 (Roa)` / `2번 · 루나 (Luna)` / `3번 · 지니 (Jinni)` / `4번 · 나루 (Naru)` / `5번 · 노바 (Nova)` 개별 검수 모드
  - `합성 · 로아 + 지니 (2인 동시)`
- **실시간 물리 제어**:
  - `바람` / `산들바람`: `@rig-c/play`의 `player.environment({ wind: [w, 0], gravity: [0, g] })`를 통해 머리카락·치마/상의 밑자락·가슴 물리 체인에 실시간 풍력 인가
  - `찰랑이기` & **캔버스 드래그**: 캐릭터를 마우스로 잡고 흔들면 관성(`player.moved({ x, y })`)에 따라 머리카락, 의상, 가슴이 실시간 반응


