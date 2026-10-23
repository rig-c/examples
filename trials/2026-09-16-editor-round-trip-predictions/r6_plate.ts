/**
 * The one plate generator every round-6 probe rig uses.
 *
 * Every plate is a checkerboard with PLACEHOLDER burned into it, drawn by the
 * repository's own tools/plate.ts. It is structurally real art -- a true size and
 * a true alpha channel -- and it is not art: no claim about seams, blending or
 * appearance can come from any of it.
 *
 * The rigc checkout is found by RIGC_ROOT, so this file survives the worktree it
 * was written in being deleted.
 */
const ROOT = process.env.RIGC_ROOT ?? (() => { throw new Error('set RIGC_ROOT to a rig-c/core checkout'); })();

type RGBA = [number, number, number, number];
const INK: RGBA = [24, 28, 36, 255];
const PAPER: RGBA = [206, 212, 226, 255];
const ACCENT: RGBA = [198, 96, 72, 255];

interface PlateLike {
  set(x: number, y: number, c: RGBA): void;
  frame(x: number, y: number, w: number, h: number, t: number, c: RGBA): void;
  textCentred(s: string, cx: number, y: number, scale: number, c: RGBA): void;
  maskAlpha(f: (x: number, y: number) => number): void;
  writePng(path: string): void;
}

export async function makePlate(path: string, width: number, height: number, label: string): Promise<void> {
  const mod = (await import(ROOT + '/tools/plate.ts')) as { Plate: new (w: number, h: number) => PlateLike };
  const plate = new mod.Plate(width, height);
  const cell = 8;
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const on = (Math.floor(x / cell) + Math.floor(y / cell)) % 2 === 0;
      plate.set(x, y, on ? PAPER : INK);
    }
  }
  plate.frame(0, 0, width, height, 1, ACCENT);
  if (height >= 20) plate.textCentred(label.toUpperCase().slice(0, 16), width / 2, Math.max(2, height / 2 - 10), 1, ACCENT);
  if (height >= 34) plate.textCentred('PLACEHOLDER', width / 2, Math.max(12, height / 2 + 2), 1, ACCENT);
  plate.maskAlpha((x, y) => (x < 2 || y < 2 || x >= width - 2 || y >= height - 2 ? 0 : 255));
  plate.writePng(path);
}
