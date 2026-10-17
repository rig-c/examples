export function releaseCandidate(candidate) {
  const errors = [];
  for (const release of [() => candidate.player.dispose(), () => candidate.assets.dispose(), () => candidate.sub.remove()]) {
    try { release(); } catch (error) { errors.push(error); }
  }
  if (errors.length) throw new AggregateError(errors, 'Outfit candidate cleanup failed');
}

/** Only the latest request for the still-active entry can transfer ownership. */
export function createOutfitTransaction({ load, current, commit, pending, failed }) {
  let generation = 0;
  const valid = (id, request) => id === generation && current(request);
  function invalidate() { generation++; pending(false); }
  async function open(request) {
    const id = ++generation;
    pending(true, request);
    let candidate = null;
    try {
      candidate = await load(request);
      if (!valid(id, request)) { const stale = candidate; candidate = null; releaseCandidate(stale); return false; }
      commit(request, candidate);
      candidate = null;
      return true;
    } catch (error) {
      if (candidate) {
        try { releaseCandidate(candidate); }
        catch (cleanup) { error = new AggregateError([error, cleanup], 'Outfit load and cleanup failed'); }
      }
      if (valid(id, request)) failed(error, request);
      return false;
    } finally {
      if (valid(id, request)) pending(false, request);
    }
  }
  return { open, invalidate };
}
