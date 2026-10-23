## Covered parts

| part | farthest px | cell | drafted radius (+3 cells) | lattice folds wind / 60° / 30° / 8° |
| --- | ---: | ---: | ---: | --- |
| fixture/hair_back | 53.4603 | 14 | 95.4603 | 0 / 12 / 0 / 0 |
| fixture/hair_front | 29.4109 | 8 | 53.4109 | 0 / 90 / 62 / 0 |
| fixture/skirt | 21.1043 | 10 | 51.1043 | 0 / 99 / 58 / 0 |
| wind/bottomwear | 81.1379 | 31 | 174.1379 | 0 / 5 / 0 / 0 |
| wind/hair_back | 133.5403 | 36 | 241.5403 | 0 / 0 / 0 / 0 |
| wind/hair_front | 61.2209 | 31 | 154.2209 | 0 / 108 / 95 / 27 |

## Sweep: folded frames per stimulus (wind / sway 60° / 30° / 8°), physics on, render --folds at 30 fps; check = rig-parts check on the rig as written, under the wind schedule

| rule | value | fixture/hair_back | fixture/hair_front | fixture/skirt | wind/bottomwear | wind/hair_back | wind/hair_front | check (fixture, wind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lattice |  | 0 / 12 / 0 / 0 | 0 / 90 / 62 / 0 | 0 / 99 / 58 / 0 | 0 / 5 / 0 / 0 | 0 / 0 / 0 / 0 | 0 / 108 / 95 / 27 | PASS, PASS |
| abs_px | 1 | r 54.4603: 0 / 0 / 0 / 0 | r 30.4109: 0 / 0 / 0 / 0 | r 22.1043: 0 / 80 / 20 / 0 | r 82.1379: 0 / 88 / 55 / 0 | r 134.5403: 0 / 0 / 0 / 0 | r 62.2209: 0 / 116 / 111 / 89 | PASS, PASS |
| abs_px | 2 | r 55.4603: 0 / 0 / 0 / 0 | r 31.4109: 0 / 0 / 0 / 0 | r 23.1043: 0 / 79 / 18 / 0 | r 83.1379: 0 / 88 / 55 / 0 | r 135.5403: 0 / 0 / 0 / 0 | r 63.2209: 0 / 116 / 111 / 85 | PASS, PASS |
| abs_px | 4 | r 57.4603: 0 / 0 / 0 / 0 | r 33.4109: 0 / 0 / 0 / 0 | r 25.1043: 0 / 73 / 13 / 0 | r 85.1379: 0 / 88 / 53 / 0 | r 137.5403: 0 / 0 / 0 / 0 | r 65.2209: 0 / 116 / 110 / 83 | PASS, PASS |
| abs_px | 8 | r 61.4603: 0 / 0 / 0 / 0 | r 37.4109: 0 / 0 / 0 / 0 | r 29.1043: 0 / 62 / 3 / 0 | r 89.1379: 0 / 74 / 38 / 0 | r 141.5403: 0 / 0 / 0 / 0 | r 69.2209: 0 / 112 / 104 / 76 | PASS, PASS |
| abs_px | 16 | r 69.4603: 0 / 0 / 0 / 0 | r 45.4109: 0 / 0 / 0 / 0 | r 37.1043: 0 / 36 / 0 / 0 | r 97.1379: 0 / 55 / 18 / 0 | r 149.5403: 0 / 0 / 0 / 0 | r 77.2209: 0 / 109 / 98 / 49 | PASS, PASS |
| abs_px | 32 | r 85.4603: 0 / 0 / 0 / 0 | r 61.4109: 0 / 0 / 0 / 0 | r 53.1043: 0 / 44 / 0 / 0 | r 113.1379: 0 / 33 / 0 / 0 | r 165.5403: 0 / 0 / 0 / 0 | r 93.2209: 0 / 99 / 83 / 13 | PASS, PASS |
| abs_px | 64 | r 117.4603: 0 / 0 / 0 / 0 | r 93.4109: 0 / 59 / 0 / 0 | r 85.1043: 0 / 56 / 0 / 0 | r 145.1379: 0 / 34 / 0 / 0 | r 197.5403: 0 / 0 / 0 / 0 | r 125.2209: 0 / 0 / 0 / 0 | PASS, PASS |
| abs_px | 128 | r 181.4603: 0 / 0 / 0 / 0 | r 157.4109: 0 / 74 / 25 / 0 | r 149.1043: 0 / 59 / 0 / 0 | r 209.1379: 0 / 47 / 0 / 0 | r 261.5403: 0 / 0 / 0 / 0 | r 189.2209: 0 / 0 / 0 / 0 | PASS, FAIL CHECK_TIP_OVER_ROOT: |
| share | 0.05 | r 56.1333: 0 / 0 / 0 / 0 | r 30.8814: 0 / 0 / 0 / 0 | r 22.1595: 0 / 80 / 19 / 0 | r 85.1948: 0 / 88 / 53 / 0 | r 140.2173: 0 / 0 / 0 / 0 | r 64.2819: 0 / 116 / 111 / 83 | PASS, PASS |
| share | 0.1 | r 58.8063: 0 / 0 / 0 / 0 | r 32.352: 0 / 0 / 0 / 0 | r 23.2147: 0 / 77 / 17 / 0 | r 89.2517: 0 / 73 / 36 / 0 | r 146.8943: 0 / 0 / 0 / 0 | r 67.343: 0 / 114 / 109 / 80 | PASS, PASS |
| share | 0.25 | r 66.8254: 0 / 0 / 0 / 0 | r 36.7636: 0 / 0 / 0 / 0 | r 26.3804: 0 / 72 / 11 / 0 | r 101.4224: 0 / 56 / 0 / 0 | r 166.9254: 0 / 0 / 0 / 0 | r 76.5261: 0 / 109 / 98 / 51 | PASS, PASS |
| share | 0.5 | r 80.1904: 0 / 0 / 0 / 0 | r 44.1164: 0 / 0 / 0 / 0 | r 31.6564: 0 / 48 / 0 / 0 | r 121.7069: 0 / 32 / 0 / 0 | r 200.3105: 0 / 0 / 0 / 0 | r 91.8314: 0 / 100 / 85 / 15 | PASS, PASS |
| share | 1 | r 106.9206: 0 / 0 / 0 / 0 | r 58.8218: 0 / 0 / 0 / 0 | r 42.2086: 0 / 40 / 0 / 0 | r 162.2758: 0 / 39 / 0 / 0 | r 267.0806: 0 / 0 / 0 / 0 | r 122.4418: 0 / 0 / 0 / 0 | PASS, PASS |
| share | 2 | r 160.3809: 0 / 0 / 0 / 0 | r 88.2327: 0 / 52 / 0 / 0 | r 63.3129: 0 / 49 / 0 / 0 | r 243.4137: 0 / 49 / 0 / 0 | r 400.6209: 0 / 0 / 0 / 0 | r 183.6627: 0 / 0 / 0 / 0 | PASS, FAIL CHECK_TIP_OVER_ROOT: |
| share | 3 | r 213.8412: 0 / 0 / 0 / 0 | r 117.6436: 0 / 68 / 10 / 0 | r 84.4172: 0 / 56 / 0 / 0 | r 324.5516: 0 / 54 / 0 / 0 | r 534.1612: 0 / 18 / 0 / 0 | r 244.8836: 0 / 0 / 0 / 0 | PASS, FAIL CHECK_TIP_OVER_ROOT: |
| cells | 0.5 | r 60.4603: 0 / 0 / 0 / 0 | r 33.4109: 0 / 0 / 0 / 0 | r 26.1043: 0 / 72 / 11 / 0 | r 96.6379: 0 / 55 / 18 / 0 | r 151.5403: 0 / 0 / 0 / 0 | r 76.7209: 0 / 109 / 98 / 51 | PASS, PASS |
| cells | 1 | r 67.4603: 0 / 0 / 0 / 0 | r 37.4109: 0 / 0 / 0 / 0 | r 31.1043: 0 / 51 / 0 / 0 | r 112.1379: 0 / 33 / 0 / 0 | r 169.5403: 0 / 0 / 0 / 0 | r 92.2209: 0 / 100 / 84 / 14 | PASS, PASS |
| cells | 2 | r 81.4603: 0 / 0 / 0 / 0 | r 45.4109: 0 / 0 / 0 / 0 | r 41.1043: 0 / 40 / 0 / 0 | r 143.1379: 0 / 34 / 0 / 0 | r 205.5403: 0 / 0 / 0 / 0 | r 123.2209: 0 / 0 / 0 / 0 | PASS, PASS |
| cells | 3 | r 95.4603: 0 / 0 / 0 / 0 | r 53.4109: 0 / 0 / 0 / 0 | r 51.1043: 0 / 44 / 0 / 0 | r 174.1379: 0 / 41 / 0 / 0 | r 241.5403: 0 / 0 / 0 / 0 | r 154.2209: 0 / 0 / 0 / 0 | PASS, PASS |
| cells | 4 | r 109.4603: 0 / 0 / 0 / 0 | r 61.4109: 0 / 0 / 0 / 0 | r 61.1043: 0 / 46 / 0 / 0 | r 205.1379: 0 / 46 / 0 / 0 | r 277.5403: 0 / 0 / 0 / 0 | r 185.2209: 0 / 0 / 0 / 0 | PASS, FAIL CHECK_TIP_OVER_ROOT: |
| cells | 6 | r 137.4603: 0 / 0 / 0 / 0 | r 77.4109: 0 / 25 / 0 / 0 | r 81.1043: 0 / 54 / 0 / 0 | r 267.1379: 0 / 49 / 0 / 0 | r 349.5403: 0 / 0 / 0 / 0 | r 247.2209: 0 / 0 / 0 / 0 | PASS, FAIL CHECK_TIP_OVER_ROOT: |
| cells | 8 | r 165.4603: 0 / 0 / 0 / 0 | r 93.4109: 0 / 59 / 0 / 0 | r 101.1043: 0 / 56 / 0 / 0 | r 329.1379: 0 / 55 / 0 / 0 | r 421.5403: 0 / 0 / 0 / 0 | r 309.2209: 0 / 0 / 0 / 0 | PASS, FAIL CHECK_TIP_OVER_ROOT: |
| cells | 11 | r 207.4603: 0 / 0 / 0 / 0 | r 117.4109: 0 / 68 / 10 / 0 | r 131.1043: 0 / 56 / 0 / 0 | r 422.1379: 0 / 58 / 0 / 0 | r 529.5403: 0 / 18 / 0 / 0 | r 402.2209: 0 / 0 / 0 / 0 | PASS, FAIL CHECK_TIP_OVER_ROOT: |

## Per rule value: does it hold on every part?

| rule | value | 0 folds, wind + 8° + 30° (the first reading's stimuli) | 0 folds, wind + 60° (#378 IF04's) | no more than the lattice, all four | checks green | parts breaking the 30° set |
| --- | --- | --- | --- | --- | --- | --- |
| abs_px | 1 | no | no | no | yes | fixture/skirt 0/20; wind/bottomwear 0/55; wind/hair_front 89/111 |
| abs_px | 2 | no | no | no | yes | fixture/skirt 0/18; wind/bottomwear 0/55; wind/hair_front 85/111 |
| abs_px | 4 | no | no | no | yes | fixture/skirt 0/13; wind/bottomwear 0/53; wind/hair_front 83/110 |
| abs_px | 8 | no | no | no | yes | fixture/skirt 0/3; wind/bottomwear 0/38; wind/hair_front 76/104 |
| abs_px | 16 | no | no | no | yes | wind/bottomwear 0/18; wind/hair_front 49/98 |
| abs_px | 32 | no | no | no | yes | wind/hair_front 13/83 |
| abs_px | 64 | yes | no | no | yes | — |
| abs_px | 128 | no | no | no | no | fixture/hair_front 0/25 |
| share | 0.05 | no | no | no | yes | fixture/skirt 0/19; wind/bottomwear 0/53; wind/hair_front 83/111 |
| share | 0.1 | no | no | no | yes | fixture/skirt 0/17; wind/bottomwear 0/36; wind/hair_front 80/109 |
| share | 0.25 | no | no | no | yes | fixture/skirt 0/11; wind/hair_front 51/98 |
| share | 0.5 | no | no | no | yes | wind/hair_front 15/85 |
| share | 1 | yes | no | no | yes | — |
| share | 2 | yes | no | no | no | — |
| share | 3 | no | no | no | no | fixture/hair_front 0/10 |
| cells | 0.5 | no | no | no | yes | fixture/skirt 0/11; wind/bottomwear 0/18; wind/hair_front 51/98 |
| cells | 1 | no | no | no | yes | wind/hair_front 14/84 |
| cells | 2 | yes | no | no | yes | — |
| cells | 3 | yes | no | no | yes | — |
| cells | 4 | yes | no | no | no | — |
| cells | 6 | yes | no | no | no | — |
| cells | 8 | yes | no | no | no | — |
| cells | 11 | no | no | no | no | fixture/hair_front 0/10 |
