import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

import { makePlate } from '../../r6_plate.ts';

const dir = join(import.meta.dir, 'parts');
mkdirSync(dir, { recursive: true });
await makePlate(join(dir, 'base.png'), 96, 72, 'base');
await makePlate(join(dir, 'mark.png'), 48, 40, 'mark');
