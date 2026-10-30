# Round 4: cut limbs with drawn round ends

`rig.json` keeps round 2's bones, constraints and animations. The four `under-*` slots are gone. Each limb part stays on one bone, with no mesh across a joint.

At each limb joint the piece that goes under gets a drawn round end: a disc about the joint, an outline stroked at the wider of the two pieces' line widths, and band fill read from the piece's own colours. The piece on top is unchanged except that its end is trimmed by one line width, so the under outline shows. Paint the top piece hides at rest takes band fill. `ops.json` lists each joint's radius, line width and drawn pixels.

Changes that are not round ends:

- Ankles: the foot now draws over the shin, because the gold cuff is painted over it. Six slots moved in draw order.
- Skirt and pelvis moved to `torso`.
- The whole pauldron moved to `front-upper-arm`; the torso under it takes fill.

Walk, 31 samples, core 2.83.0's seam reader: six of 16 mapped rows are above 0, all of them background beside the limbs and at least 11.0 px from the pivot.
