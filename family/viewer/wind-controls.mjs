export const BASE_WIND_LIMIT = 6;
export const WIND_LIMIT = 12;
export const GUST_DURATION = 2.4;
export const GUST_PEAK = 12;
export const GUST_PERIOD = 6;

/** Consumer-side wind timing; the player remains the only physics solver. */
export function createWindControls() {
  let base = 0;
  let breeze = false;
  let repeat = false;
  let time = 0;
  let gustStart = null;
  let gustDirection = 1;
  let nextGust = null;

  function triggerGust() {
    // Keep the current pulse continuous, including after the base changes sign.
    if (read().gusting) return;
    gustStart = time;
    gustDirection = base < 0 ? -1 : 1;
    if (repeat) nextGust = time + GUST_PERIOD;
  }

  function read() {
    const age = gustStart === null ? GUST_DURATION : time - gustStart;
    const gusting = age >= 0 && age < GUST_DURATION;
    const gust = gusting ? gustDirection * GUST_PEAK * Math.sin(Math.PI * age / GUST_DURATION) ** 2 : 0;
    const gentle = breeze ? 2 * Math.sin(2.2 * time) + 0.8 * Math.sin(5.1 * time) : 0;
    const wind = Math.max(-WIND_LIMIT, Math.min(WIND_LIMIT, base + gentle + gust));
    return { base, breeze, repeat, time, gust, gusting, wind };
  }

  return {
    read,
    setBase(value) {
      if (!Number.isFinite(value)) throw new RangeError('base wind must be finite');
      base = Math.max(-BASE_WIND_LIMIT, Math.min(BASE_WIND_LIMIT, value));
    },
    setBreeze(value) { breeze = Boolean(value); },
    triggerGust,
    setRepeat(value) {
      const enabled = Boolean(value);
      if (enabled === repeat) return;
      repeat = enabled;
      if (repeat) {
        if (read().gusting) nextGust = gustStart + GUST_PERIOD;
        else triggerGust();
      }
      else nextGust = null; // Let the pulse already in flight finish smoothly.
    },
    advance(dt) {
      if (!Number.isFinite(dt) || dt < 0) throw new RangeError('wind dt must be finite and non-negative');
      time += dt;
      if (repeat && time >= nextGust) {
        gustStart = nextGust + Math.floor((time - nextGust) / GUST_PERIOD) * GUST_PERIOD;
        gustDirection = base < 0 ? -1 : 1;
        nextGust = gustStart + GUST_PERIOD;
      }
      return read();
    },
  };
}
