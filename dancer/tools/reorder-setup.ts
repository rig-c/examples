/** Preserve the accepted projection; apply the active config's authored setup order before rig generation. */
import { writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';
const [runtime, directory, source, config, mode] = process.argv.slice(2);
if (!runtime || !directory || !source || !config || (mode !== undefined && mode !== '--dry')) throw Error('USAGE: runtime parts-directory painting config [--dry]');
const moduleAt = (name: string) => import(pathToFileURL(resolve(runtime, 'node_modules/@rig-c/parts/src', name)).href);
const { loadConfig } = await moduleAt('config.ts');
const { readParts, serializeParts } = await moduleAt('parts.ts');
const { stageFields, drawOrder, measureRecomposite, recompositeRecord, sourceInRig } = await moduleAt('assemble.ts');
const { flatComposite } = await moduleAt('check.ts');
const { readPng, writePng } = await moduleAt('raster/png.ts');
const cfg = loadConfig(config), fields = stageFields(cfg), parts = readParts(join(directory, 'parts.json'));
if (cfg.limbs || parts.alternates?.length || fields.patches.length) throw Error('SETUP_ORDER_SCOPE: this example owns its existing plan and cuts only');
const names = drawOrder(fields.plan.map((p: string[]) => p[0]), fields.patches, fields.cuts).map((slot: {plan?: number; cut?: number; patch?: number}) => slot.plan !== undefined ? fields.plan[slot.plan][0] : fields.cuts[slot.cut!].into);
const byName = new Map(parts.parts.map((part: {name: string}) => [part.name, part]));
if (new Set(names).size !== names.length || names.length !== byName.size || names.some((n: string) => !byName.has(n))) throw Error('SETUP_ORDER_MEMBERS: authored order must name every existing part once');
const before = parts.parts.map((part: {name: string}) => part.name);
parts.parts = names.map((name: string) => byName.get(name));
const images = parts.parts.map((record: {name: string; w: number; h: number}) => {
  const image = readPng(join(directory, 'parts', record.name + '.png'));
  if (image.width !== record.w || image.height !== record.h) throw Error('SETUP_ORDER_IMAGE: ' + record.name);
  return {record, image};
});
if (mode !== '--dry') {
  const composite = flatComposite(parts, join(directory, 'parts'), [255, 255, 255, 255]);
  const painting = sourceInRig(readPng(source), ...parts.rig_size);
  parts.recomposite = recompositeRecord(measureRecomposite(composite, painting, images));
  writeFileSync(join(directory, 'parts.json'), serializeParts(parts));
  writePng(join(directory, 'recomposite_rig.png'), composite);
}
console.log(JSON.stringify({source: config, before, after: names, partRecordsAndPngsUnchanged: true, dry: mode === '--dry'}));
