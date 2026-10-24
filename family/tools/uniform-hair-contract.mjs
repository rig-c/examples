import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';

export const clothingSlots = ['topwear', 'bottomwear', 'legwear', 'shoes', 'sleeves', 'handwear_l', 'handwear_r', 'neckwear'];
const excluded = new Set([...clothingSlots, 'neck']);
const fields = ['mass', 'strength', 'damping', 'inertia', 'wind'];

/** Compare every shared draw, including order and non-coordinate geometry inputs. */
export function assertSharedDrawsEqual(office, uniform) {
  const shared = frame => frame.order.filter(draw => !excluded.has(draw.slot));
  const a = shared(office), b = shared(uniform);
  assert.ok(a.length > 0, 'UNIFORM_SHARED_EMPTY');
  assert.deepEqual(b.map(draw => draw.slot), a.map(draw => draw.slot), 'UNIFORM_SHARED_ORDER');
  for (let index = 0; index < a.length; index++) {
    // Absolute z positions and page UVs describe outfit layout, not posed geometry.
    const geometry = draw => Object.fromEntries(Object.entries(draw).filter(([key]) => !['z', 'page', 'pma', 'uvs', 'region'].includes(key)));
    assert.deepEqual(geometry(b[index]), geometry(a[index]), `UNIFORM_SHARED_GEOMETRY ${a[index].slot}`);
    const coordinates = a[index].vertices ?? a[index].corners;
    assert.ok(Array.isArray(coordinates) && coordinates.length > 0 && coordinates.every(Number.isFinite), `UNIFORM_SHARED_COORDINATES ${a[index].slot}`);
  }
  return { draws: a.length, coordinates: a.reduce((sum, draw) => sum + (draw.vertices ?? draw.corners).length, 0), exact: true };
}

/** Full-document equality permits only the declared scalars and derived model pin. */
export function assertUniformPhysicsOnly(before, after, profile, { spineText } = {}) {
  assert.ok(profile.constraints.length > 0, 'UNIFORM_PHYSICS_EMPTY');
  const expected = structuredClone(before), names = new Set();
  const targets = before.constraints.filter(c => (c.type ?? c.kind) === 'physics' && /^(hair|bang)/.test(c.bone));
  assert.deepEqual(profile.constraints.map(c => `${c.name}\0${c.bone}`).sort(), targets.map(c => `${c.name}\0${c.bone}`).sort(), 'UNIFORM_PHYSICS_TARGET_SET');
  for (const row of profile.constraints) {
    assert.ok(!names.has(row.name), 'UNIFORM_PHYSICS_DUPLICATE');
    names.add(row.name);
    for (const side of ['before', 'after']) {
      assert.deepEqual(Object.keys(row[side]).sort(), [...fields].sort(), 'UNIFORM_PHYSICS_FIELDS');
      assert.ok(fields.every(field => Number.isFinite(row[side][field])), 'UNIFORM_PHYSICS_FINITE');
    }
    const matches = expected.constraints.filter(c => c.name === row.name && c.bone === row.bone && (c.type ?? c.kind) === 'physics');
    assert.equal(matches.length, 1, `UNIFORM_PHYSICS_TARGET ${row.name}`);
    for (const field of fields) {
      assert.equal(matches[0][field], row.before[field], `UNIFORM_PHYSICS_PREIMAGE ${row.name}/${field}`);
      matches[0][field] = row.after[field];
    }
  }
  if (spineText !== undefined) expected.spine.sha256 = createHash('sha256').update(spineText).digest('hex');
  assert.deepEqual(after, expected, 'UNIFORM_PHYSICS_OUTSIDE_ALLOWLIST');
  return { constraints: names.size, fields: names.size * fields.length, allOtherFieldsEqual: true };
}
