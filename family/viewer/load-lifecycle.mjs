/** A request owns its detached stage and resources until the newest one publishes. */
export function createSceneLoader({ createStage, loadAssets, createEntry, publish, loading, failed }) {
  let generation = 0;
  let pending = null;
  let active = null;

  function release(scene) {
    if (!scene) return [];
    scene.cancelled = true;
    const errors = [];
    for (const record of scene.records) {
      if (record.released) continue;
      record.released = true;
      try { record.entry.player.dispose(); } catch (error) { errors.push(error); }
      try { record.assets.dispose(); } catch (error) { errors.push(error); }
    }
    try { scene.stage.remove(); } catch (error) { errors.push(error); }
    return errors;
  }

  const current = scene => scene.generation === generation && !scene.cancelled;

  async function open(request) {
    const id = ++generation;
    const cleanup = [...release(pending), ...release(active)];
    pending = null;
    active = null;
    loading(request);
    if (cleanup.length) {
      failed(new AggregateError(cleanup, 'Previous scene cleanup failed'));
      return;
    }
    const scene = { generation: id, stage: createStage(), records: [], cancelled: false };
    pending = scene;
    const tasks = request.lineup.map(async item => {
      let assets;
      try {
        assets = await loadAssets(item, request);
        if (!current(scene)) {
          assets.dispose();
          return null;
        }
        let entry;
        try { entry = createEntry(item, assets, scene.stage); }
        catch (error) {
          try { assets.dispose(); }
          catch (cleanupError) { throw new AggregateError([error, cleanupError], 'Player creation and asset cleanup failed'); }
          throw error;
        }
        scene.records.push({ entry, assets, released: false });
        return entry;
      } catch (error) {
        if (current(scene)) {
          const errors = release(scene);
          if (pending === scene) pending = null;
          failed(errors.length ? new AggregateError([error, ...errors], 'Scene load and cleanup failed') : error);
        }
        throw error;
      }
    });
    // Attach handlers to every sibling, including those finishing after a refusal.
    const results = await Promise.allSettled(tasks);
    if (!current(scene)) return;
    if (results.some(result => result.status === 'rejected')) return;
    pending = null;
    active = scene;
    try { publish(request, scene.stage, results.map(result => result.value)); }
    catch (error) {
      const errors = release(scene);
      active = null;
      failed(errors.length ? new AggregateError([error, ...errors], 'Scene publication and cleanup failed') : error);
    }
  }

  function dispose() {
    generation++;
    const errors = [...release(pending), ...release(active)];
    pending = null;
    active = null;
    if (errors.length) throw new AggregateError(errors, 'Scene cleanup failed');
  }

  return { open, dispose };
}
