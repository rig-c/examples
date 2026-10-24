/** Hash-bound office material stage; existing declared repairs keep their original preimages. */
import { createHash } from 'node:crypto';
const digest = value => createHash('sha256').update(JSON.stringify(value)).digest('hex');
const fields = ['mass', 'strength', 'damping', 'inertia', 'wind'];
const fail = (label, detail) => { throw Error(`REPRODUCIBILITY_PROFILE_${label} ${detail}`); };

export function validateMaterialProfile(profile, character, outfit) {
  if (!profile || profile.spec !== 'family-material-profile/1' || outfit !== 'office' || profile.character !== character || profile.outfit !== outfit || !Array.isArray(profile.constraints) || profile.constraints.length === 0) fail('SCHEMA', `${character}/${outfit}`);
  const names = new Set();
  for (const row of profile.constraints) {
    const hair = /^(hair|bang)/.test(row.bone);
    const skirt = character === 'jinni' && /^skirt_/.test(row.bone);
    if (typeof row.name !== 'string' || names.has(row.name) || (!hair && !skirt)) fail('TARGET', String(row.name));
    names.add(row.name);
    for (const side of ['before', 'after']) {
      if (!row[side] || Object.keys(row[side]).sort().join() !== [...fields].sort().join() || fields.some(f => !Number.isFinite(row[side][f]))) fail('FIELDS', row.name);
    }
    const b = row.before;
    const expected = { mass: hair ? .45 : .7, strength: b.strength * (hair ? 1.1 : .75), damping: b.damping + (hair ? -.06 : .02), inertia: b.inertia * (hair ? .85 : 1.2), wind: b.wind * (hair ? 1.4 : 2.5) };
    for (const f of fields) if (row.after[f] !== Number(expected[f].toFixed(6))) fail('VALUE', `${row.name}/${f}`);
  }
  for (const stage of ['raw', 'repaired']) for (const side of ['before', 'after']) if (!/^[a-f0-9]{64}$/.test(profile[stage]?.[side])) fail('HASH', `${stage}/${side}`);
}

/** Only five declared scalar fields may move; full-rig hashes bind both sides. */
export function materialProfileRig(rig, profile, stage, direction) {
  if (!['raw', 'repaired'].includes(stage) || !['forward', 'reverse'].includes(direction)) fail('DIRECTION', `${stage}/${direction}`);
  validateMaterialProfile(profile, profile.character, profile.outfit);
  const from = direction === 'forward' ? 'before' : 'after';
  const to = direction === 'forward' ? 'after' : 'before';
  if (digest(rig) !== profile[stage][from]) fail('INPUT_DRIFT', `${profile.character}/${stage}/${from}`);
  const result = structuredClone(rig);
  const targets = result.constraints.filter(c => c.type === 'physics' && (/^(hair|bang)/.test(c.bone) || (profile.character === 'jinni' && /^skirt_/.test(c.bone))));
  if (targets.length !== profile.constraints.length) fail('TARGET_SET', profile.character);
  for (const row of profile.constraints) {
    const matches = targets.filter(c => c.name === row.name && c.bone === row.bone);
    if (matches.length !== 1) fail('TARGET', row.name);
    for (const f of fields) {
      if (matches[0][f] !== row[from][f]) fail('PREIMAGE', `${row.name}/${f}`);
      matches[0][f] = row[to][f];
    }
  }
  if (digest(result) !== profile[stage][to]) fail('OUTPUT_DRIFT', `${profile.character}/${stage}/${to}`);
  return result;
}

/** Uniform shares the accepted office hair, while clothing keeps its own profile. */
export function validateUniformHairProfile(profile, officeProfile, character, outfit) {
  if (!profile || profile.spec !== 'family-uniform-hair-profile/1' || outfit !== 'uniform' || profile.outfit !== outfit || profile.character !== character || officeProfile?.character !== character || profile.officeProfileSHA256 !== digest(officeProfile)) fail('UNIFORM_SCHEMA', `${character}/${outfit}`);
  validateMaterialProfile(officeProfile, character, 'office');
  const expected = officeProfile.constraints.filter(row => /^(hair|bang)/.test(row.bone));
  if (expected.length === 0 || JSON.stringify(profile.constraints) !== JSON.stringify(expected)) fail('UNIFORM_TARGETS', character);
  if (!profile.repaired || Object.keys(profile.repaired).sort().join() !== 'after,before' || ['before', 'after'].some(side => !/^[a-f0-9]{64}$/.test(profile.repaired[side]))) fail('UNIFORM_HASH', character);
}

/** Runs after existing outfit repairs; every non-profile field remains hash-bound. */
export function uniformHairProfileRig(rig, profile, officeProfile, direction) {
  validateUniformHairProfile(profile, officeProfile, profile?.character, profile?.outfit);
  if (!['forward', 'reverse'].includes(direction)) fail('UNIFORM_DIRECTION', String(direction));
  const from = direction === 'forward' ? 'before' : 'after';
  const to = direction === 'forward' ? 'after' : 'before';
  if (digest(rig) !== profile.repaired[from]) fail('UNIFORM_INPUT_DRIFT', `${profile.character}/${from}`);
  const result = structuredClone(rig);
  const targets = result.constraints.filter(c => c.type === 'physics' && /^(hair|bang)/.test(c.bone));
  if (targets.length !== profile.constraints.length) fail('UNIFORM_TARGET_SET', profile.character);
  for (const row of profile.constraints) {
    const matches = targets.filter(c => c.name === row.name && c.bone === row.bone);
    if (matches.length !== 1) fail('UNIFORM_TARGET', row.name);
    for (const field of fields) {
      if (matches[0][field] !== row[from][field]) fail('UNIFORM_PREIMAGE', `${row.name}/${field}`);
      matches[0][field] = row[to][field];
    }
  }
  if (digest(result) !== profile.repaired[to]) fail('UNIFORM_OUTPUT_DRIFT', `${profile.character}/${to}`);
  return result;
}
