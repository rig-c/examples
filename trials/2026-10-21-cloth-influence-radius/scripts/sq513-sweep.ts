// rig-c/parts#513 reading (parts#513 sweep): per covered part, the farthest lattice vertex from its nearest link as
// the tree measures it, then a sweep of influence radii = farthest + margin in three forms; per variant: rig, rigc
// build, render --folds with physics on under #378's stimuli, and rig-parts check.
// Usage: bun sq513-sweep.ts <worktree> <workdir> <fixture|wind> [variant-id,...]
import { cpSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const [WT, WORK, SUBJECT, ONLY] = process.argv.slice(2);
const { CLOTH_PARTS, CLOTH_RIG, clothRecipe } = await import(join(WT, 'fixtures/cloth.ts'));
const { writeProposeFixture } = await import(join(WT, 'fixtures/propose.ts'));
const { proposeWithBasis, readPartSet, DEFAULT_GRID_RULE } = await import(join(WT, 'src/propose.ts'));
const { pyRound } = await import(join(WT, 'src/round.ts'));
const RIGC = join(WT, 'node_modules/.bin/rigc');
const root = join(WORK, SUBJECT);
mkdirSync(root, { recursive: true });

type Mesh = Record<string, unknown> & { segments: unknown[]; grid?: number; influence?: { cell: number; radius: number; across: boolean; max: number; shape: string } };
type Cfg = Record<string, unknown> & { meshes: Record<string, Mesh> };
let lattice: Cfg; // the config as proposed without influence (the lattice baseline)
let drafted: Cfg; // the config as propose --cloth drafts it with influence declared (farthest + 3 cells)
let partsDir: string;
const farthest: Record<string, number> = {};
const DECL = { across: true, max: 6, shape: 'smooth' };

async function run(cmd: string[], cwd = WT): Promise<{ status: number; out: string }> {
  const p = Bun.spawn(cmd, { cwd, stdout: 'pipe', stderr: 'pipe' });
  const [o, e] = await Promise.all([new Response(p.stdout).text(), new Response(p.stderr).text()]);
  return { status: await p.exited, out: o + e };
}

if (SUBJECT === 'fixture') {
  partsDir = join(root, 'parts');
  if (!existsSync(join(partsDir, 'parts.json'))) writeProposeFixture(partsDir, CLOTH_PARTS, CLOTH_RIG);
  const P = readPartSet(partsDir);
  const asCfg = (prop: Record<string, unknown> & { meshes: Record<string, Mesh>; constraints?: unknown[]; limbs?: unknown }): Cfg => ({
    key: 'fixture',
    assemble: { rig_scale: 1, plan: CLOTH_PARTS.map((p: { name: string; from: string }) => [p.name, ...p.from.split(':')]) },
    bones: prop.bones, meshes: prop.meshes, regions: prop.regions,
    ...(prop.limbs === undefined ? {} : { limbs: prop.limbs }),
    motion: prop.motion, constraints: prop.constraints ?? [],
  });
  lattice = asCfg(proposeWithBasis(P, undefined, null, DEFAULT_GRID_RULE, clothRecipe()).proposal);
  const recipe = clothRecipe() as Record<string, Record<string, unknown>>;
  for (const t of Object.keys(recipe)) recipe[t].influence = { ...DECL };
  const d = proposeWithBasis(P, undefined, null, DEFAULT_GRID_RULE, recipe);
  drafted = asCfg(d.proposal);
  // The farthest distance: the draft's own LINT finding, influenceFarthest (src/rig.ts), the figure RIG_INFLUENCE_REACH reads.
  for (const f of d.draftLint as Array<{ kind: string; part: string; farthest: number }>) if (f.kind === 'influence-radius') farthest[f.part] = f.farthest;
} else {
  partsDir = join(WORK, 'wind-parts', 'rig');
  lattice = JSON.parse(readFileSync(join(WT, 'examples/wind/config.json'), 'utf8'));
  const g = lattice.generation as { control: { skeleton: string } };
  g.control.skeleton = join(WT, 'examples/wind', g.control.skeleton);
  const prop = JSON.parse(readFileSync(join(WORK, 'wind-prop', 'proposal.json'), 'utf8')) as { meshes: Record<string, Mesh> };
  drafted = { ...lattice, meshes: prop.meshes };
  // The wind proposal's LINT lines carry the same finding; read back from the saved propose output.
  for (const l of readFileSync(join(WORK, 'wind-prop.out'), 'utf8').split('\n')) {
    const m = /^LINT (\w+) on mesh .*= farthest ([\d.]+) \+ 3 × cell/.exec(l);
    if (m) farthest[m[1]] = Number(m[2]);
  }
}
const covered = Object.entries(drafted.meshes).filter(([, m]) => m.influence !== undefined).map(([p]) => p).sort();
if (covered.length === 0 || covered.some((p) => farthest[p] === undefined)) throw new Error(`no farthest for ${covered}`);
const cell = (p: string): number => (drafted.meshes[p].influence as { cell: number }).cell;

const RULES: Array<{ rule: string; values: number[]; radius: (d: number, c: number, v: number) => number }> = [
  { rule: 'abs_px', values: [1, 2, 4, 8, 16, 32, 64, 128], radius: (d, _c, v) => d + v },
  { rule: 'share', values: [0.05, 0.1, 0.25, 0.5, 1, 2, 3], radius: (d, _c, v) => d * (1 + v) },
  { rule: 'cells', values: [0.5, 1, 2, 3, 4, 6, 8, 11], radius: (d, c, v) => d + v * c },
];
type Variant = { id: string; rule: string; value: number | null; radii: Record<string, number> | null };
const variants: Variant[] = [{ id: 'lattice', rule: 'lattice', value: null, radii: null }];
for (const R of RULES) for (const v of R.values) variants.push({ id: `${R.rule}-${v}`, rule: R.rule, value: v, radii: Object.fromEntries(covered.map((p) => [p, pyRound(R.radius(farthest[p], cell(p), v), 4)])) });
const chosen = ONLY === undefined ? variants : variants.filter((v) => ONLY.split(',').includes(v.id));

function configWith(radii: Record<string, number> | null): Cfg {
  if (radii === null) return lattice;
  const meshes = { ...drafted.meshes };
  for (const [p, r] of Object.entries(radii)) meshes[p] = { ...meshes[p], influence: { ...(meshes[p].influence as NonNullable<Mesh['influence']>), radius: r } };
  return { ...drafted, meshes };
}

const envFile = join(root, 'wind-env.json');
writeFileSync(envFile, JSON.stringify({ spec: 'rigc-environment/1', steps: [{ t: 0, wind: [1, 0] }, { t: 1.1, wind: [-1, 0] }, { t: 2.2, wind: [0, 0] }] }));
// #378 IF04's stimuli: the idle under wind +1, -1, calm, and a hip sway of 60 degrees; 30 and 8 degrees as the first reading also swept.
const SWAYS = [60, 30, 8];
const sway = (deg: number) => ({ duration: 4, tracks: [{ bone: 'hip', property: 'rotate', keys: Array.from({ length: 49 }, (_, i) => ({ t: pyRound(i / 12, 6), v: [pyRound(deg * Math.sin((2 * Math.PI * i) / 24), 4)] })) }] });

async function measure(v: Variant): Promise<Record<string, unknown>> {
  const dir = join(root, v.id);
  mkdirSync(dir, { recursive: true });
  const cfg = join(dir, 'config.json');
  writeFileSync(cfg, JSON.stringify(configWith(v.radii)));
  const rig = await run(['bun', join(WT, 'cli.ts'), 'rig', '--config', cfg, '--parts', partsDir, '--out', join(dir, 'rig')]);
  writeFileSync(join(dir, 'rig.out'), rig.out);
  if (rig.status !== 0) return { ...v, error: `rig exit ${rig.status}: ${rig.out.split('\n').filter((l) => l.includes('FAIL')).join(' | ').slice(0, 600)}` };
  // The check verdict on the rig as the rig stage wrote it (its own idle), under the wind schedule.
  const chk = await run(['bun', join(WT, 'cli.ts'), 'check', '--rig', join(dir, 'rig'), '--parts', partsDir, '--out', join(dir, 'check'), '--environment', envFile]);
  writeFileSync(join(dir, 'check.out'), chk.out);
  const failLines = chk.out.split('\n').filter((l) => /^\s*FAIL\b/.test(l)).map((l) => l.trim().split(/\s+/)[1]);
  const foldLine = chk.out.split('\n').find((l) => l.includes('ANIMATIONS_DO_NOT_FOLD'))?.trim() ?? null;
  // The stimuli on a scratch copy.
  const sdir = join(dir, 'stim');
  cpSync(join(dir, 'rig'), sdir, { recursive: true });
  const m = JSON.parse(readFileSync(join(sdir, 'motion.json'), 'utf8'));
  m.animations = m.animations ?? {};
  for (const d of SWAYS) m.animations[`sway${d}`] = sway(d);
  writeFileSync(join(sdir, 'motion.json'), JSON.stringify(m));
  const build = join(dir, 'build');
  const b = await run([RIGC, 'build', '--rig', join(sdir, 'rig.json'), '--motion', join(sdir, 'motion.json'), '--out', build, '--profile', 'rig-play', '--copy-images']);
  if (b.status !== 0) return { ...v, error: `rigc build exit ${b.status}: ${b.out.slice(-600)}` };
  const stimuli: Array<[string, string, string | null]> = [['wind', 'idle', envFile], ...SWAYS.map((d) => [`sway${d}`, `sway${d}`, null] as [string, string, null])];
  const folds: Record<string, Record<string, { frames: number; worst: number }>> = {};
  for (const [k, anim, env] of stimuli) {
    const out = join(dir, `render-${k}`);
    const r = await run([RIGC, 'render', '--candidate', build, '--animation', anim, '--fps', '30', '--max', '64', '--folds', '--out', out, ...(env === null ? [] : ['--environment', env])]);
    if (r.status !== 0) return { ...v, error: `render ${k} exit ${r.status}: ${r.out.slice(-600)}` };
    const rows = JSON.parse(readFileSync(join(out, `${anim}@30fps`, 'folds.json'), 'utf8')).meshes as Array<{ slot: string; frames: unknown[]; worst: { triangles: unknown[] } | null }>;
    folds[k] = Object.fromEntries(rows.map((x) => [x.slot, { frames: x.frames.length, worst: x.worst === null ? 0 : x.worst.triangles.length }]));
  }
  const report = JSON.parse(readFileSync(join(dir, 'rig', 'mesh_report.json'), 'utf8')) as Array<Record<string, unknown>>;
  return {
    ...v, check: { exit: chk.status, fails: failLines, fold_line: foldLine }, folds,
    mesh: Object.fromEntries(report.filter((r) => covered.includes(r.part as string)).map((r) => [r.part, { mode: r.mode ?? 'lattice', vertices: r.vertices, triangles: r.triangles, max_influences: r.max_influences, reach: r.reach ?? null }])),
  };
}

const results: Record<string, unknown>[] = [];
const queue = [...chosen];
const JOBS = Number(process.env.SQ513_JOBS ?? '3');
await Promise.all(Array.from({ length: JOBS }, async () => {
  for (let v = queue.shift(); v !== undefined; v = queue.shift()) {
    const r = await measure(v);
    results.push(r);
    console.log(`${SUBJECT} ${v.id}: ${r.error ?? `check exit ${(r.check as { exit: number }).exit}`}`);
  }
}));
results.sort((a, b) => variants.findIndex((v) => v.id === a.id) - variants.findIndex((v) => v.id === b.id));
const rigcV = (await run([RIGC, '--version'])).out.split('\n')[0];
writeFileSync(join(WORK, `${SUBJECT}-results${ONLY === undefined ? '' : '-partial'}.json`), JSON.stringify({ subject: SUBJECT, covered, farthest, cells: Object.fromEntries(covered.map((p) => [p, cell(p)])), drafted_radii: Object.fromEntries(covered.map((p) => [p, (drafted.meshes[p].influence as { radius: number }).radius])), rigc: rigcV, results }, null, 1));
console.log(JSON.stringify({ covered, farthest }));
