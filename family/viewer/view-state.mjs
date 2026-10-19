export const STORAGE_KEY = 'rig-c-family-viewer:v2';
export const CHARACTERS = ['all5', 'all5_wide', 'roa', 'luna', 'jinni', 'naru', 'nova', 'composed'];
export const OUTFIT_CHARACTERS = ['roa', 'luna', 'jinni', 'naru', 'nova'];
export function defaultViewState() {
  return { version: 2, character: 'all5', background: 'dark', comparison: true, paused: false,
    speed: 1, gravity: 0, bones: false, mesh: false, meshOpacity: 0.55, cameras: {}, wind: null,
    outfits: { roa: 'office', luna: 'office', jinni: 'office', naru: 'office', nova: 'office' } };
}
const finite = (v, lo, hi) => typeof v === 'number' && Number.isFinite(v) && v >= lo && v <= hi;
export function readViewState(storage) {
  const result = defaultViewState();
  try {
    const saved = JSON.parse(storage?.getItem(STORAGE_KEY) ?? 'null');
    if (saved?.version !== 2) return result;
    if (CHARACTERS.includes(saved.character)) result.character = saved.character;
    for (const key of OUTFIT_CHARACTERS) {
      if (['office', 'homewear', 'swimwear', 'uniform'].includes(saved.outfits?.[key])) result.outfits[key] = saved.outfits[key];
    }
    if (['dark', 'white', 'grey', 'magenta'].includes(saved.background)) result.background = saved.background;
    for (const key of ['comparison', 'paused', 'bones', 'mesh']) if (typeof saved[key] === 'boolean') result[key] = saved[key];
    for (const [key, lo, hi] of [['speed', .1, 2.5], ['gravity', -3, 3], ['meshOpacity', 0, 1]]) if (finite(saved[key], lo, hi)) result[key] = saved[key];
    for (const [key, camera] of Object.entries(saved.cameras ?? {})) {
      if (CHARACTERS.includes(key) && finite(camera?.zoom, .05, 100) && finite(camera?.x, -1e7, 1e7) && finite(camera?.y, -1e7, 1e7)) result.cameras[key] = { ...camera };
    }
    if (saved.wind && typeof saved.wind === 'object') result.wind = saved.wind;
  } catch { /* A storage refusal or obsolete record must not prevent loading. */ }
  return result;
}
export function writeViewState(storage, state) {
  try { storage?.setItem(STORAGE_KEY, JSON.stringify(state)); return true; } catch { return false; }
}
