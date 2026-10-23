import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

import { makePlate } from '../../r6_plate.ts';

const dir = join(import.meta.dir, 'parts');
mkdirSync(dir, { recursive: true });
// Four deliberately different shapes, so the packer has to place them at four
// different offsets on the shared page rather than in a row of equal cells.
await makePlate(join(dir, 'wide.png'), 120, 40, 'wide');
await makePlate(join(dir, 'tall.png'), 40, 112, 'tall');
await makePlate(join(dir, 'small.png'), 36, 36, 'small');
await makePlate(join(dir, 'odd.png'), 68, 52, 'odd');
