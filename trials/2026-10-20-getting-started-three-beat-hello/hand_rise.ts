// How far the right hand rises in an animation: pose a build with spine-core at 24 fps and follow
// the forearm image's lowest drawn point at the setup pose (the hand), the sleeve_r1 bone's tip, and
// the image's lowest point frame by frame. World units, y up; 1 unit is 1 rig px on this rig.
//
//   bun hand_rise.ts <build dir with skeleton.json and skeleton.atlas> [animation]
import * as sc from '@esotericsoftware/spine-core';
import { readFileSync } from 'node:fs';
const dir = process.argv[2], anim = process.argv[3] ?? 'hello', fps = 24;
const atlas = new sc.TextureAtlas(readFileSync(dir + '/skeleton.atlas', 'utf8'));
const data = new sc.SkeletonJson(new sc.AtlasAttachmentLoader(atlas)).readSkeletonData(readFileSync(dir + '/skeleton.json', 'utf8'));
const sk = new sc.Skeleton(data);
const a = data.findAnimation(anim)!;
const slot = sk.findSlot('forearm_r')!;
const bone = sk.findBone('sleeve_r1')!;
const rows: number[][] = [];
let distal: {x:number,y:number}|null = null;
const n = Math.round(a.duration * fps);
for (let i = 0; i <= n; i++) {
  const t = i / fps;
  const state = new sc.AnimationState(new sc.AnimationStateData(data));
  state.setAnimation(0, anim, false);
  sk.setupPose(); sk.update(0); sk.updateWorldTransform(sc.Physics.reset);
  state.update(t); state.apply(sk); sk.update(t); sk.updateWorldTransform(sc.Physics.update);
  const att = slot.appliedPose.attachment as sc.RegionAttachment;
  const v = new Float32Array(8);
  att.computeWorldVertices(slot, att.getOffsets(slot.appliedPose), v, 0, 2);
  const ys = [v[1], v[3], v[5], v[7]];
  const tip = { x: bone.appliedPose.worldX + bone.data.length * bone.appliedPose.a, y: bone.appliedPose.worldY + bone.data.length * bone.appliedPose.c };
  const bp = bone.appliedPose;
  if (distal === null) { // the bottom-centre of the forearm image at rest (the hand's lowest drawn point), in the bone's frame
    const wx = (v[0]+v[2]+v[4]+v[6])/4, wy = Math.min(...ys);
    const dx = wx - bp.worldX, dy = wy - bp.worldY, det = bp.a*bp.d - bp.b*bp.c;
    distal = { x: (dx*bp.d - dy*bp.b)/det, y: (dy*bp.a - dx*bp.c)/det };
  }
  const hy = distal.x*bp.c + distal.y*bp.d + bp.worldY;
  rows.push([i, t, Math.min(...ys), Math.max(...ys), tip.y, hy]);
}
const r0 = rows[0];
let best = rows[0];
for (const r of rows) if (r[2] - r0[2] > best[2] - r0[2]) best = r;
let bestTip = rows[0];
for (const r of rows) if (r[4] - r0[4] > bestTip[4] - r0[4]) bestTip = r;
let bestH = rows[0];
for (const r of rows) if (r[5] - r0[5] > bestH[5] - r0[5]) bestH = r;
console.log(JSON.stringify({ handPoint: { restY: r0[5], frame: bestH[0], t: bestH[1], y: bestH[5], rise: bestH[5]-r0[5] }, frames: rows.length, rest: { regionLowestY: r0[2], regionHighestY: r0[3], boneTipY: r0[4] },
  regionLowestRise: { frame: best[0], t: best[1], y: best[2], rise: best[2] - r0[2], highestY: best[3] },
  boneTipRise: { frame: bestTip[0], t: bestTip[1], y: bestTip[4], rise: bestTip[4] - r0[4] } }, null, 1));
