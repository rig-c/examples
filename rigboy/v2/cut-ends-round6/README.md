# Round 6: ankle motion

Images are round 5's, byte for byte. Only `rig.json` and `motion.json` changed, and each limb part stays on one bone.

The leg is 134 long on a hip 142 high, against 204 on 247 in the source, and its shin is shorter than its thigh where the source's is longer. So the same foot path bent the knee further and laid the shin back, which read as a hinged boot.

Three changes, all to foot-path geometry; no bone length moved:

- `hip` y +7 in the setup pose, so the leg stands straighter. Every animation carries it.
- `front-foot-target` x +30 in the setup pose, so the shin leans forward as the source's does. Every animation carries it.
- `walk`: the x of both foot targets' translate keys × 0.85, 7 keys each with their curves. Stride and ground speed drop 15 %.

Walk, 31 samples: shin-to-foot bend within 13.8° of the source on the front leg and 12.0° on the rear, from 35.6° and 21.1°. 0 background pixels at all 12 joint discs. Stripping the fills from one knee and one elbow reads 489 and 201 px, so the disc fires.

The front leg now sits forward of the rear one: the feet are 130 px apart at one double support and 80 at the other, where round 5 had 130 and 124.
