# Round 4: cut limbs with drawn round ends

`rig.json` keeps round 2's bones, constraints and animations. The four `under-*` slots are gone. Each limb part stays on one bone, with no mesh across a joint.

At each limb joint the piece that goes under gets a drawn round end: a disc about the joint, an outline stroked at the wider of the two pieces' line widths, and band fill read from the piece's own colours. The piece on top is unchanged except that its end is trimmed by one line width, so the under outline shows. Paint the top piece hides at rest takes band fill. `ops.json` lists each joint's radius, line width and drawn pixels.

Changes that are not round ends:

- Ankles: the foot now draws over the shin, because the gold cuff is painted over it. Six slots moved in draw order.
- Skirt and pelvis moved to `torso`.
- The whole pauldron moved to `front-upper-arm`; the torso under it takes fill.

The cap's disc on the pivot reaches half the limb's width + .25 + the joint's registration offset, so it stays put under rotation. A fill never invents gold, and a warm component under 30 px is residue.

`gun.png` is 122×67, its drawn size, area-averaged on premultiplied pixels: the one region under 0.5 scale, which aliased at 730×400 with no mipmaps. Its width, height and scale stay in `rig.json`, so world size is unchanged (`downsampled.json`).

Walk, 31 samples, joint disc of half the limb's fitted width, capped by the pivot's distance to the painted silhouette (`disc-radii.json`): 0 background pixels at all 12 joints. Stripping the drawn end from one knee and one elbow reads 1141 and 250 px, so the disc fires.
