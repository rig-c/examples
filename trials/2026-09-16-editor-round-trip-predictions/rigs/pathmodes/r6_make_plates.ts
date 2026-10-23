import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

import { makePlate } from '../../r6_plate.ts';

const dir = join(import.meta.dir, 'parts');
mkdirSync(dir, { recursive: true });
await makePlate(join(dir, 'link_a.png'), 48, 40, 'link a');
await makePlate(join(dir, 'link_b.png'), 40, 36, 'link b');
await makePlate(join(dir, 'tag.png'), 44, 40, 'tag');
