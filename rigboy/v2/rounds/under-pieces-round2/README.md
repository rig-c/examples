# Round 2: moved joints and under-pieces

`rig.json` moves five bones' setup positions so the hip and shoulder joints sit on the painted joints: `hip`, `front-thigh`, `rear-thigh`, `front-shoulder`, `back-shoulder` (`moved-bones.json`). Rotations, constraints and animations are unchanged.

Four region slots give open seams material beneath both neighbours. Each PNG is an exact RGBA crop of a neighbour's texture.

| Slot | Bone | Copied from | Drawn directly below |
| --- | --- | --- | --- |
| `under-rear-wrist` | `gun` | `rear-bracer` | `rear-bracer` |
| `under-rear-hip` | `torso` | `rear-thigh` | `rear-thigh` |
| `under-rear-knee` | `rear-shin` | `rear-thigh` | `rear-thigh` |
| `under-groin` | `torso` | `front-thigh` | `torso` |

`rear-upper-arm.png` replaces 499 texels of pink See-through filler, for the section hidden behind the torso, with the arm's own texels on one line across the arm. `arm-fill.json` lists them.

`torso:rear-thigh` remains open by 3 px at two walk frames, because no neighbouring art of the right material covers those cells.
