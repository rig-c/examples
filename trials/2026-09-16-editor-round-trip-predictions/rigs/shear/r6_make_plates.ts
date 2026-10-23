import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

import { makePlate } from '../../r6_plate.ts';

const dir = join(import.meta.dir, 'parts');
mkdirSync(dir, { recursive: true });
await makePlate(join(dir, 'pin.png'), 48, 48, 'pin');
await makePlate(join(dir, 'lean.png'), 56, 64, 'lean');
await makePlate(join(dir, 'tip.png'), 40, 40, 'tip');
await makePlate(join(dir, 'side.png'), 44, 52, 'side');
