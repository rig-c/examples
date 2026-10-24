// Read the actual accepted fixtures through the real toolchain readers.
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';

const [core, sequence, payload] = process.argv.slice(2);
if (!core || !sequence || !payload) throw new Error('INPUT_PATH: core, sequence and payload required');
const { parseRigSpec } = await import(pathToFileURL(resolve(core, 'src/rig.ts')).href);
const { parseMotionSpec } = await import(pathToFileURL(resolve(core, 'src/motion.ts')).href);
const { readPoseSequence } = await import(pathToFileURL(resolve(process.env.POSE_READER_FILE ?? resolve(core, '../@rig-c/pose/src/pose.ts'))).href);
const rig = parseRigSpec(JSON.parse(await Bun.file(resolve(payload, 'rig.json')).text()), 'accepted-v3-rig');
const motion = parseMotionSpec(JSON.parse(await Bun.file(resolve(payload, 'motion.json')).text()), 'accepted-v3-motion');
const pose = readPoseSequence(await Bun.file(sequence).text(), 'accepted-source-sequence');
if (pose.frames.length !== 313 || pose.frames.some((frame: { t: number }, index: number) => Math.abs(frame.t - index / 24) > 0.000004)) throw new Error('INPUT_SEQUENCE: expected 313 timestamps on the declared 24fps grid');
let rejected = false;
try { parseRigSpec({ spec: 'invalid-fixture' }, 'planted-invalid-rig'); } catch { rejected = true; }
if (!rejected) throw new Error('INPUT_READER: planted invalid rig was accepted');
console.log(JSON.stringify({ realReaders: true, bones: rig.bones.length, animations: Object.keys(motion.animations).length, frames: pose.frames.length, declaredFPS: 24, plantedInvalidRejected: rejected }));
