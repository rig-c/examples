import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

import { makePlate } from '../../r6_plate.ts';

const dir = join(import.meta.dir, 'parts');
mkdirSync(dir, { recursive: true });
await makePlate(join(dir, 'plain.png'), 56, 48, 'plain');
await makePlate(join(dir, 'dressed.png'), 56, 48, 'dressed');
// The region whose placeholder is badge_alt: the PNG keeps its own name, so the
// emitted attachment carries a `path` that differs from the placeholder.
await makePlate(join(dir, 'badge.png'), 36, 36, 'badge');
await makePlate(join(dir, 'panel.png'), 64, 48, 'panel');
