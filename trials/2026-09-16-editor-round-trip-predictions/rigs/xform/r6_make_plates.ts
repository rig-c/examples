import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

import { makePlate } from '../../r6_plate.ts';

const dir = join(import.meta.dir, 'parts');
mkdirSync(dir, { recursive: true });
await makePlate(join(dir, 'src.png'), 64, 56, 'src');
await makePlate(join(dir, 'dst.png'), 64, 56, 'dst');
await makePlate(join(dir, 'tag.png'), 40, 36, 'tag');
