/**
 * Round trip 6's verdict reader.
 *
 *   bun read.ts --rig <name> --build <dir|file> --export <dir|file>
 *   bun read.ts --all --out <round6/out>          (every rig that has a run)
 *   bun read.ts --selfcheck                       (the reader's own controls)
 *
 * It prints one line per prediction row: CONFIRMED / REFUTED / AMBIGUOUS, with
 * the observed value beside the predicted one.
 *
 * 🔒 Three rules hold it to being a measurement rather than a rationalisation.
 *
 * 1. **Every expectation comes out of predictions.json.** Nothing observed is
 *    written here. A row names a probe, a list of competing hypotheses and which
 *    one it predicts; this file only resolves the probe on two skeletons and
 *    reports which hypotheses survive.
 * 2. **A hypothesis is an expected OBSERVATION, derived from the build.** So
 *    "kept" means "the export's value equals the build's", and the reader can
 *    work out, before any editor has run, whether two hypotheses would look the
 *    same on this rig.
 * 3. **When more than one surviving hypothesis matches, the verdict is
 *    AMBIGUOUS, never the one we hoped for.** That is the whole reason #539's
 *    two rigs were trustworthy: each printed AMBIGUOUS alone, and only their
 *    intersection named a comparator. A row whose hypotheses coincide on this
 *    rig is a rig that cannot answer its own question, and the line says so.
 *
 * A row that matches NO hypothesis prints REFUTED and says that nothing on the
 * table predicted what came back — the #540 shape, and the honest state.
 */
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { basename, dirname, join, resolve } from 'node:path';

type Json = Record<string, unknown>;

const isObj = (v: unknown): v is Json => typeof v === 'object' && v !== null && !Array.isArray(v);

/** What a probe found: whether the field was there at all, and what it held. */
interface Found {
  present: boolean;
  value: unknown;
}

const MISSING: Found = { present: false, value: undefined };

/**
 * The editor's measured comparator: natural order, case-insensitive (#539).
 * Here so an ORDER hypothesis can be stated as "the order the editor writes"
 * rather than as a literal list somebody typed.
 */
function editorOrder(names: string[]): string[] {
  const key = (s: string): Array<string | number> => {
    const parts: Array<string | number> = [];
    for (const m of s.toLowerCase().matchAll(/(\d+)|(\D+)/g)) {
      parts.push(m[1] !== undefined ? Number(m[1]) : m[2]);
    }
    return parts;
  };
  return [...names].sort((a, b) => {
    const ka = key(a);
    const kb = key(b);
    for (let i = 0; i < Math.max(ka.length, kb.length); i++) {
      const x = ka[i];
      const y = kb[i];
      if (x === undefined) return -1;
      if (y === undefined) return 1;
      if (typeof x === 'number' && typeof y === 'number') {
        if (x !== y) return x - y;
      } else {
        const sx = String(x);
        const sy = String(y);
        if (sx !== sy) return sx < sy ? -1 : 1;
      }
    }
    return a < b ? -1 : a > b ? 1 : 0;
  });
}

function codepointOrder(names: string[]): string[] {
  return [...names].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
}

// ---------------------------------------------------------------------------
// probes
// ---------------------------------------------------------------------------

function attachmentsOf(skel: Json, slot: string, placeholder: string): Found {
  for (const skin of (skel.skins as Json[] | undefined) ?? []) {
    const atts = skin.attachments;
    if (!isObj(atts)) continue;
    const bySlot = atts[slot];
    if (!isObj(bySlot)) continue;
    if (placeholder in bySlot) return { present: true, value: bySlot[placeholder] };
  }
  return MISSING;
}

function namedFrom(list: unknown, name: string): Found {
  if (!Array.isArray(list)) return MISSING;
  for (const entry of list) {
    if (isObj(entry) && entry.name === name) return { present: true, value: entry };
  }
  return MISSING;
}

function field(found: Found, path: string[]): Found {
  let cur = found;
  for (const key of path) {
    if (!cur.present) return MISSING;
    if (Array.isArray(cur.value) && /^\d+$/.test(key)) {
      const i = Number(key);
      if (i >= cur.value.length) return MISSING;
      cur = { present: true, value: cur.value[i] };
      continue;
    }
    if (!isObj(cur.value) || !(key in cur.value)) return MISSING;
    cur = { present: true, value: (cur.value as Json)[key] };
  }
  return cur;
}

function names(list: unknown): string[] {
  return Array.isArray(list) ? list.map((e) => (isObj(e) ? String(e.name) : String(e))) : [];
}

/**
 * Resolve one probe string against one skeleton.
 *
 * The grammar is small on purpose: every form below is a thing a round trip can
 * lose or move, and nothing here can express a computation, so a row cannot
 * smuggle an answer into its own probe.
 */
export function probe(skel: Json, expr: string): Found {
  const rest = (s: string): string[] => (s === '' ? [] : s.replace(/^\./, '').split('.'));

  let m = /^skeleton\.(.+)$/.exec(expr);
  if (m) return field({ present: true, value: skel.skeleton }, rest(m[1]));

  m = /^count\.(\w+)$/.exec(expr);
  if (m) {
    const c = skel[m[1]];
    if (Array.isArray(c)) return { present: true, value: c.length };
    if (isObj(c)) return { present: true, value: Object.keys(c).length };
    return { present: true, value: 0 };
  }

  m = /^order\.(\w+)$/.exec(expr);
  if (m) {
    const c = skel[m[1]];
    if (Array.isArray(c)) return { present: true, value: names(c) };
    if (isObj(c)) return { present: true, value: Object.keys(c) };
    return MISSING;
  }

  m = /^bone\[([^\]]+)\](.*)$/.exec(expr);
  if (m) return field(namedFrom(skel.bones, m[1]), rest(m[2]));

  m = /^slot\[([^\]]+)\](.*)$/.exec(expr);
  if (m) return field(namedFrom(skel.slots, m[1]), rest(m[2]));

  m = /^constraint\[([^\]]+)\](.*)$/.exec(expr);
  if (m) return field(namedFrom(skel.constraints, m[1]), rest(m[2]));

  m = /^att\[([^/\]]+)\/([^\]]+)\](.*)$/.exec(expr);
  if (m) return field(attachmentsOf(skel, m[1], m[2]), rest(m[3]));

  m = /^anim\[([^\]]+)\]\.groups$/.exec(expr);
  if (m) {
    const anims = skel.animations;
    if (!isObj(anims) || !isObj(anims[m[1]])) return MISSING;
    return { present: true, value: Object.keys(anims[m[1]] as Json) };
  }

  m = /^anim\[([^\]]+)\]\.(\w+)\[([^\]]+)\](.*)$/.exec(expr);
  if (m) {
    const anims = skel.animations;
    if (!isObj(anims)) return MISSING;
    const anim = anims[m[1]];
    if (!isObj(anim)) return MISSING;
    // `bone` and `slot` are spelled in the plural in the file.
    const group = m[2] === 'bone' ? 'bones' : m[2] === 'slot' ? 'slots' : m[2];
    const byName = anim[group];
    if (!isObj(byName) || !(m[3] in byName)) return MISSING;
    return field({ present: true, value: byName[m[3]] }, rest(m[4]));
  }

  m = /^anim\[([^\]]+)\]\.(\w+)(\..*)?$/.exec(expr);
  if (m) {
    const anims = skel.animations;
    if (!isObj(anims)) return MISSING;
    const anim = anims[m[1]];
    if (!isObj(anim) || !(m[2] in anim)) return MISSING;
    return field({ present: true, value: anim[m[2]] }, rest(m[3] ?? ''));
  }

  throw new Error(`read.ts: no probe grammar matches ${JSON.stringify(expr)}`);
}

// ---------------------------------------------------------------------------
// hypotheses
// ---------------------------------------------------------------------------

interface Expect {
  /** The build's own value came back unchanged. */
  kept?: true;
  /**
   * The field is there, whatever it holds.
   *
   * ⭐ The form most of this table needs, and the reason is issue #535: the
   * editor rewrote `animations.curve_kinds` on 196 of 200 keys in both of its
   * round trips, unexplained. A row that compares a whole key array would come
   * back REFUTED on every rig for that reason and say nothing about the question
   * it was asked. "Did this timeline survive at all" is separable from "are its
   * numbers the same", so they are separate rows.
   */
  presentOnly?: true;
  /** The field is not in the export at all. */
  absent?: true;
  /** A literal the row states. */
  value?: unknown;
  /** The build list, re-ordered by the comparator #539 measured. */
  editorSorted?: true;
  /** The build list, re-ordered by UTF-16 code units. */
  codepointSorted?: true;
  /** The build value with these object keys removed (a partial loss). */
  without?: string[];
}

interface Hypothesis {
  name: string;
  expect: Expect;
  /** Why anybody would expect this. Printed, never used in the comparison. */
  why?: string;
}

interface Row {
  id: string;
  rig: string;
  question: string;
  probe: string;
  /** 'doc' | 'inferred' | 'none' — where the prediction comes from. */
  basis: string;
  basisNote?: string;
  predict: string;
  hypotheses: Hypothesis[];
  /** Absolute tolerance for numeric comparison. Default: exact. */
  tolerance?: number;
  /** A fixed-point control: a row whose job is to fail when everything is lost. */
  control?: true;
}

function expected(e: Expect, build: Found): Found {
  if (e.presentOnly) return { present: true, value: '(any value)' };
  if (e.kept) return build;
  if (e.absent) return MISSING;
  if (e.value !== undefined) return { present: true, value: e.value };
  if (e.editorSorted) {
    if (!build.present || !Array.isArray(build.value)) return MISSING;
    return { present: true, value: editorOrder(build.value as string[]) };
  }
  if (e.codepointSorted) {
    if (!build.present || !Array.isArray(build.value)) return MISSING;
    return { present: true, value: codepointOrder(build.value as string[]) };
  }
  if (e.without) {
    if (!build.present || !isObj(build.value)) return MISSING;
    const copy: Json = {};
    for (const [k, v] of Object.entries(build.value)) if (!e.without.includes(k)) copy[k] = v;
    return { present: true, value: copy };
  }
  throw new Error(`read.ts: a hypothesis states no expectation: ${JSON.stringify(e)}`);
}

function near(a: unknown, b: unknown, tol: number): boolean {
  if (typeof a === 'number' && typeof b === 'number') return Math.abs(a - b) <= tol;
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((x, i) => near(x, b[i], tol));
  }
  if (isObj(a) && isObj(b)) {
    const ka = Object.keys(a);
    const kb = Object.keys(b);
    if (ka.length !== kb.length) return false;
    return ka.every((k) => k in b && near(a[k], (b as Json)[k], tol));
  }
  return JSON.stringify(a) === JSON.stringify(b);
}

function same(a: Found, b: Found, tol: number): boolean {
  if (a.present !== b.present) return false;
  if (!a.present) return true;
  return near(a.value, b.value, tol);
}

function show(f: Found): string {
  if (!f.present) return '(absent)';
  const s = JSON.stringify(f.value);
  return s === undefined ? String(f.value) : s.length > 96 ? `${s.slice(0, 93)}...` : s;
}

export interface Verdict {
  row: Row;
  verdict: 'CONFIRMED' | 'REFUTED' | 'AMBIGUOUS';
  matched: string[];
  observed: Found;
  predictedShown: string;
  note: string;
}

export function judge(row: Row, build: Json, exported: Json): Verdict {
  const tol = row.tolerance ?? 0;
  const b = probe(build, row.probe);
  const x = probe(exported, row.probe);
  const matched: string[] = [];
  let predictedShown = '(the prediction names no hypothesis on the table)';
  for (const h of row.hypotheses) {
    const e = expected(h.expect, b);
    if (h.name === row.predict) predictedShown = show(e);
    const hit = h.expect.presentOnly === true ? x.present : same(e, x, tol);
    if (hit) matched.push(h.name);
  }
  if (matched.length === 0) {
    return {
      row,
      verdict: 'REFUTED',
      matched,
      observed: x,
      predictedShown,
      note: 'no hypothesis on the table predicted this observation',
    };
  }
  if (matched.length > 1) {
    return {
      row,
      verdict: 'AMBIGUOUS',
      matched,
      observed: x,
      predictedShown,
      note: `this rig cannot separate ${matched.join(' / ')} — they predict the same observation here`,
    };
  }
  return {
    row,
    verdict: matched[0] === row.predict ? 'CONFIRMED' : 'REFUTED',
    matched,
    observed: x,
    predictedShown,
    note: matched[0] === row.predict ? '' : `what came back is ${matched[0]}`,
  };
}

// ---------------------------------------------------------------------------
// files and the command line
// ---------------------------------------------------------------------------

function skeletonAt(path: string): Json {
  let p = resolve(path);
  if (statSync(p).isDirectory()) {
    const direct = join(p, 'skeleton.json');
    if (existsSync(direct)) p = direct;
    else {
      const json = readdirSync(p).filter((f) => f.endsWith('.json'));
      if (json.length === 0) throw new Error(`read.ts: no .json in ${p}`);
      p = join(p, json[0]);
    }
  }
  return JSON.parse(readFileSync(p, 'utf8')) as Json;
}

function loadRows(file: string): Row[] {
  const doc = JSON.parse(readFileSync(file, 'utf8')) as { rows?: Row[] };
  if (!Array.isArray(doc.rows)) throw new Error(`read.ts: ${file} carries no rows array`);
  return doc.rows;
}

const BASIS_MARK: Record<string, string> = { doc: 'doc', inferred: 'inferred', none: 'NO BASIS' };

function report(rows: Row[], build: Json, exported: Json, label: string): number {
  console.log(`## ${label}   ${rows.length} row(s)`);
  let bad = 0;
  for (const row of rows) {
    const v = judge(row, build, exported);
    if (v.verdict !== 'CONFIRMED') bad++;
    const tag = row.control ? ' [control]' : '';
    console.log(
      `  ${v.verdict.padEnd(9)} ${row.id.padEnd(10)} ${row.question}${tag}\n` +
        `      basis=${BASIS_MARK[row.basis] ?? row.basis}  predicted(${row.predict})=${v.predictedShown}\n` +
        `      observed=${show(v.observed)}${v.note === '' ? '' : `\n      ${v.note}`}`,
    );
  }
  return bad;
}

function main(): void {
  const argv = process.argv.slice(2);
  const flags = new Map<string, string>();
  const bare = new Set<string>();
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith('--')) continue;
    const key = a.slice(2);
    const next = argv[i + 1];
    if (next === undefined || next.startsWith('--')) bare.add(key);
    else {
      flags.set(key, next);
      i++;
    }
  }
  const here = import.meta.dir;
  const predictions = flags.get('predictions') ?? join(here, 'predictions.json');

  if (bare.has('selfcheck')) {
    selfcheck(here);
    return;
  }

  const rows = loadRows(predictions);

  if (bare.has('all')) {
    const outRoot = flags.get('out') ?? join(here, 'out');
    let bad = 0;
    let ran = 0;
    for (const name of readdirSync(outRoot).sort()) {
      const buildDir = join(outRoot, name, 'build');
      const exportDir = join(outRoot, name, 'roundtrip', 'export');
      if (!existsSync(buildDir) || !existsSync(exportDir)) {
        console.log(`## ${name}   NOT RUN — no ${existsSync(buildDir) ? 'export' : 'build'} under ${join(outRoot, name)}`);
        continue;
      }
      ran++;
      bad += report(rows.filter((r) => r.rig === name), skeletonAt(buildDir), skeletonAt(exportDir), name);
    }
    if (ran === 0) {
      console.error('read.ts: nothing was measured — no rig under --out has both a build and an export');
      process.exit(2);
    }
    process.exit(bad === 0 ? 0 : 1);
  }

  const rig = flags.get('rig');
  const build = flags.get('build');
  const exported = flags.get('export');
  if (rig === undefined || build === undefined || exported === undefined) {
    console.error('usage: bun read.ts --rig <name> --build <dir|file> --export <dir|file>');
    console.error('       bun read.ts --all [--out <dir>]');
    console.error('       bun read.ts --selfcheck');
    process.exit(2);
  }
  const mine = rows.filter((r) => r.rig === rig);
  if (mine.length === 0) {
    console.error(`read.ts: predictions.json carries no row for rig "${rig}"`);
    process.exit(2);
  }
  const bad = report(mine, skeletonAt(build), skeletonAt(exported), rig);
  process.exit(bad === 0 ? 0 : 1);
}

/**
 * The reader's own controls, and all three branches have to fire.
 *
 * ⭐ A verdict tool nobody has seen print REFUTED is the same shape as a gate
 * nobody has seen fail. So this runs the rows three ways:
 *
 *   identity  — an editor export measured against ITSELF. Every `kept` row must
 *               be CONFIRMED; it is the only branch whose data was made by a
 *               real editor, and it comes from the pass-1 exports.
 *   lost      — the same build against an export with the constraints, the
 *               animations' extra groups and the non-region attachments stripped.
 *               Every row must come back REFUTED.
 *   coincide  — a row whose hypotheses predict the same observation on this rig.
 *               It must print AMBIGUOUS, never the hoped-for name.
 */
function selfcheck(here: string): void {
  const rows = loadRows(join(here, 'predictions.json'));
  const failures: string[] = [];

  // --- identity, on data a real editor wrote -------------------------------
  const exportsDir = flags_exportsDir();
  const pass1 = join(exportsDir, 'nod.export.json');
  if (existsSync(pass1)) {
    const skel = JSON.parse(readFileSync(pass1, 'utf8')) as Json;
    const ident: Row[] = [
      {
        id: 'SELF-ID1',
        rig: 'selfcheck',
        question: 'an editor export measured against itself keeps its bone order',
        probe: 'order.bones',
        basis: 'inferred',
        predict: 'kept',
        hypotheses: [
          { name: 'kept', expect: { kept: true } },
          { name: 'lost', expect: { absent: true } },
        ],
      },
      {
        id: 'SELF-ID2',
        rig: 'selfcheck',
        question: 'and its slot count',
        probe: 'count.slots',
        basis: 'inferred',
        predict: 'kept',
        hypotheses: [
          { name: 'kept', expect: { kept: true } },
          { name: 'zero', expect: { value: 0 } },
        ],
      },
    ];
    for (const row of ident) {
      const v = judge(row, skel, skel);
      console.log(`  identity  ${v.verdict.padEnd(9)} ${row.id}  ${row.question}`);
      if (v.verdict !== 'CONFIRMED') failures.push(`${row.id} printed ${v.verdict}, wanted CONFIRMED`);
    }
    // And the same export against a pass-1 BUILD, which is a row that genuinely
    // applies across a real round trip rather than against itself.
    const galNod = process.env.R6_GALLERY_NOD ?? '';
    if (galNod !== '' && existsSync(galNod)) {
      const build = skeletonAt(galNod);
      const row: Row = {
        id: 'SELF-RT1',
        rig: 'selfcheck',
        question: 'pass-1 nod: the editor returned the bones array element for element',
        probe: 'order.bones',
        basis: 'inferred',
        basisNote: 'AUTHORING 10.1, measured on the pass-1 trip',
        predict: 'kept',
        hypotheses: [
          { name: 'kept', expect: { kept: true } },
          { name: 'editorSorted', expect: { editorSorted: true } },
          { name: 'lost', expect: { absent: true } },
        ],
      };
      const v = judge(row, build, skel);
      console.log(`  pass1     ${v.verdict.padEnd(9)} ${row.id}  ${row.question}`);
      console.log(`            matched=${v.matched.join('/') || '(none)'}  observed=${show(v.observed)}`);
      if (v.verdict === 'REFUTED' && v.matched.length === 0) {
        failures.push('SELF-RT1 matched no hypothesis — read the note, the build and the export may be different eras');
      }
    }
  } else {
    failures.push(`no pass-1 export at ${pass1}; the identity control had nothing real to run on`);
  }

  // --- everything lost ------------------------------------------------------
  const anyRig = process.env.R6_SELFCHECK_RIG ?? rows[0]?.rig;
  // A build to strip: the run's own if there is one, else the preparation build.
  const candidates = [join(here, 'out', anyRig, 'build'), join(here, 'tmp', `r6_build_${anyRig}`)];
  const buildPath = candidates.find((p) => existsSync(p)) ?? candidates[candidates.length - 1];
  if (existsSync(buildPath)) {
    const build = skeletonAt(buildPath);
    const lost = JSON.parse(JSON.stringify(build)) as Json;
    delete lost.constraints;
    for (const skin of (lost.skins as Json[] | undefined) ?? []) {
      const atts = skin.attachments;
      if (!isObj(atts)) continue;
      for (const [slot, byName] of Object.entries(atts)) {
        if (!isObj(byName)) continue;
        for (const [name, att] of Object.entries(byName)) {
          if (isObj(att) && att.type !== undefined && att.type !== 'region') delete (atts[slot] as Json)[name];
        }
      }
    }
    for (const anim of Object.values((lost.animations as Json | undefined) ?? {})) {
      if (!isObj(anim)) continue;
      for (const g of Object.keys(anim)) if (g !== 'bones') delete anim[g];
    }
    delete (lost.skeleton as Json).referenceScale;
    for (const slot of (lost.slots as Json[] | undefined) ?? []) {
      delete slot.dark;
      delete slot.blend;
      delete slot.color;
    }
    const mine = rows.filter((r) => r.rig === anyRig);
    let sawRefuted = 0;
    for (const row of mine) {
      const v = judge(row, build, lost);
      if (v.verdict === 'REFUTED') sawRefuted++;
      console.log(`  lost      ${v.verdict.padEnd(9)} ${row.id}  ${row.question}`);
    }
    if (sawRefuted === 0) failures.push(`the "everything lost" export produced no REFUTED row on ${anyRig}`);
  } else {
    failures.push(`no build to strip at ${buildPath}`);
  }

  // --- a row that cannot separate its hypotheses ----------------------------
  const coincide: Row = {
    id: 'SELF-AMB',
    rig: 'selfcheck',
    question: 'two hypotheses that predict the same observation on this rig',
    probe: 'order.animations',
    basis: 'none',
    predict: 'kept',
    hypotheses: [
      { name: 'kept', expect: { kept: true } },
      { name: 'editorSorted', expect: { editorSorted: true }, why: 'already in that order, so it cannot be told apart' },
    ],
  };
  const one = { animations: { alpha: {}, beta: {} } } as unknown as Json;
  const v = judge(coincide, one, one);
  console.log(`  coincide  ${v.verdict.padEnd(9)} ${coincide.id}  ${coincide.question}`);
  if (v.verdict !== 'AMBIGUOUS') failures.push(`SELF-AMB printed ${v.verdict}, wanted AMBIGUOUS`);

  console.log('');
  if (failures.length === 0) {
    console.log('selfcheck: every branch fired — CONFIRMED, REFUTED and AMBIGUOUS were all printed');
    process.exit(0);
  }
  for (const f of failures) console.error(`selfcheck FAIL: ${f}`);
  process.exit(1);
}

/** Where the pass-1 exports live; overridable so this is not one machine's path. */
function flags_exportsDir(): string {
  return process.env.R6_EXPORTS ?? resolve(import.meta.dir, '..', 'exports');
}

main();

export { editorOrder, codepointOrder, basename, dirname };
