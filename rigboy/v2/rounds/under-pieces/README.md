# Under-pieces for rigboy v2

Five region slots that give a seam material beneath both of its neighbours. Each PNG is an exact RGBA crop of a neighbour's texture, on the same 416x624 canvas, placed at that texture's setup-relative frame on the other neighbour's bone. No pixel is painted or resampled.

| Slot | Bone | Copied from | Drawn directly below |
| --- | --- | --- | --- |
| `under-rear-wrist-bracer` | `rear-bracer` | `rigboy-rear-gauntlet` | `rear-bracer` |
| `under-rear-wrist-gun` | `gun` | `rear-bracer` | `rear-bracer` |
| `under-rear-knee` | `rear-shin` | `rear-thigh` | `rear-thigh` |
| `under-groin` | `front-thigh` | `torso` | `torso` |
| `under-front-ankle` | `front-foot` | `front-shin` | `front-foot` |

`rig.json` is the rig spec with these five slots added; bones, constraints and animations are unchanged. `under-design.json` records each crop's size and local frame.

The crops close the measured seams but are not clean by eye: the groin and front-ankle pieces show as small scraps at some frames.
