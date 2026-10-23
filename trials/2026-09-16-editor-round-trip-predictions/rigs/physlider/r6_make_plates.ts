import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

import { makePlate } from '../../r6_plate.ts';

const dir = join(import.meta.dir, 'parts');
mkdirSync(dir, { recursive: true });
await makePlate(join(dir, 'tag.png'), 48, 44, 'tag');
await makePlate(join(dir, 'gate.png'), 40, 64, 'gate');
await makePlate(join(dir, 'mark.png'), 44, 40, 'mark');
