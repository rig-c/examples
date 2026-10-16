export const BASE_WIND_LIMIT = 100;
export const MAX_GUST_PEAK = 200;
export const MIN_GUST_DURATION = 0.1;
export const MAX_GUST_DURATION = 20;
export const GUST_DURATION = 2.4;
export const GUST_PEAK = 48;
export const GUST_PERIOD = 6;
// A derived UI envelope, never an extra clamp on the requested environment.
export const WIND_LIMIT = BASE_WIND_LIMIT + MAX_GUST_PEAK + 2.8;

const bounded = (value, min, max, name) => {
  if (!Number.isFinite(value) || value < min || value > max) {
    throw new RangeError(`${name} must be finite and within [${min}, ${max}]`);
  }
  return value;
};

/** Consumer-side stress timing; the player remains the only physics solver. */
export function createWindControls() {
  let base = 0;
  let breeze = false;
  let repeat = false;
  let time = 0;
  let gustStart = null;
  let gustDirection = 1;
  let nextGust = null;
  let gustPeak = GUST_PEAK;
  let gustDuration = GUST_DURATION;
  let activeGustPeak = GUST_PEAK;
  let activeGustDuration = GUST_DURATION;
  const period = duration => Math.max(GUST_PERIOD, duration + 0.6);

  function start(at) {
    gustStart = at;
    gustDirection = base < 0 ? -1 : 1;
    activeGustPeak = gustPeak;
    activeGustDuration = gustDuration;
    if (repeat) nextGust = at + period(activeGustDuration);
  }

  function triggerGust() {
    // A click cannot interrupt a pulse or hide a sign-change stress result.
    if (!read().gusting) start(time);
  }

  function read() {
    const age = gustStart === null ? activeGustDuration : time - gustStart;
    const gusting = age >= 0 && age < activeGustDuration;
    const gust = gusting ? gustDirection * activeGustPeak * Math.sin(Math.PI * age / activeGustDuration) ** 2 : 0;
    const gentle = breeze ? 2 * Math.sin(2.2 * time) + 0.8 * Math.sin(5.1 * time) : 0;
    return { base, breeze, repeat, time, gust, gusting, wind: base + gentle + gust,
      gustPeak, gustDuration, activeGustPeak, activeGustDuration };
  }

  function snapshot() {
    return { version: 1, base, breeze, repeat, gustPeak, gustDuration };
  }

  function restore(value) {
    const s = value === null ? { version: 1, base: 0, breeze: false, repeat: false, gustPeak: GUST_PEAK, gustDuration: GUST_DURATION } : value;
    if (!s || typeof s !== 'object' || Array.isArray(s) || s.version !== 1) throw new RangeError('wind snapshot must be a version 1 object');
    // Validate the complete configuration before changing the standing state.
    const nextBase = bounded(s.base, -BASE_WIND_LIMIT, BASE_WIND_LIMIT, 'base wind');
    const nextPeak = bounded(s.gustPeak, 0, MAX_GUST_PEAK, 'gust peak');
    const nextDuration = bounded(s.gustDuration, MIN_GUST_DURATION, MAX_GUST_DURATION, 'gust duration');
    if (typeof s.breeze !== 'boolean' || typeof s.repeat !== 'boolean') throw new RangeError('wind snapshot breeze and repeat must be booleans');
    base = nextBase; gustPeak = nextPeak; gustDuration = nextDuration;
    breeze = s.breeze; repeat = s.repeat;
    time = 0; gustStart = null; gustDirection = 1; nextGust = null;
    activeGustPeak = gustPeak; activeGustDuration = gustDuration;
    // Reload retains the chosen test configuration and begins a fresh test.
    if (repeat) start(0);
  }

  return {
    read, snapshot, restore,
    setBase(value) { base = bounded(value, -BASE_WIND_LIMIT, BASE_WIND_LIMIT, 'base wind'); },
    setGustPeak(value) { gustPeak = bounded(value, 0, MAX_GUST_PEAK, 'gust peak'); },
    setGustDuration(value) { gustDuration = bounded(value, MIN_GUST_DURATION, MAX_GUST_DURATION, 'gust duration'); },
    setBreeze(value) { breeze = Boolean(value); },
    triggerGust,
    setRepeat(value) {
      const enabled = Boolean(value);
      if (enabled === repeat) return;
      repeat = enabled;
      if (repeat) {
        if (read().gusting) nextGust = gustStart + period(activeGustDuration);
        else start(time);
      } else nextGust = null; // Finish the active pulse before returning to base.
    },
    advance(dt) {
      if (!Number.isFinite(dt) || dt < 0 || !Number.isFinite(time + dt)) throw new RangeError('wind dt must be finite, non-negative and keep a finite clock');
      time += dt;
      if (repeat && nextGust !== null && time >= nextGust) {
        const interval = period(gustDuration);
        start(nextGust + Math.floor((time - nextGust) / interval) * interval);
      }
      return read();
    },
  };
}
