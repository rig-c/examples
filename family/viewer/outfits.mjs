export const NARU_OUTFITS = ['office', 'homewear'];
export function outfitAssets(character, outfit = 'office') {
  if (!['roa', 'luna', 'jinni', 'naru', 'nova'].includes(character)) throw new Error(`Unknown character: ${character}`);
  if (!NARU_OUTFITS.includes(outfit) || (character !== 'naru' && outfit !== 'office')) throw new Error(`Unsupported outfit: ${character}/${outfit}`);
  const root = character === 'naru' && outfit === 'homewear' ? '/outfits/homewear/naru' : `/${character}`;
  return { modelUrl: `${root}/out/check/build/skeleton.model.json`, referenceUrl: `${root}/inputs/painting.png` };
}

/** The scene loader keeps this owner while a stable entry changes its player. */
export function ownAssets(assets) {
  const owner = { current: assets };
  return { owner, assets: { ...assets, dispose() {
    const current = owner.current;
    owner.current = null;
    current?.dispose();
  } } };
}
