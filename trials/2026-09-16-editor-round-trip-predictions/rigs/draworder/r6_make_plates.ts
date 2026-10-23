import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

import { makePlate } from '../../r6_plate.ts';

const dir = join(import.meta.dir, 'parts');
mkdirSync(dir, { recursive: true });
await makePlate(join(dir, 'back.png'), 80, 64, 'back');
await makePlate(join(dir, 'mid.png'), 64, 56, 'mid');
await makePlate(join(dir, 'front.png'), 48, 48, 'front');
await makePlate(join(dir, 'flag.png'), 40, 40, 'flag');
