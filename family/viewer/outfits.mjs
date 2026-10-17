export const OUTFIT_CHARACTERS = ['roa', 'luna', 'jinni', 'naru', 'nova'];
export const OUTFITS = ['office', 'homewear'];
export const NARU_OUTFITS = OUTFITS;
export function outfitAssets(character, outfit = 'office') {
  if (!OUTFIT_CHARACTERS.includes(character)) throw new Error(`Unknown character: ${character}`);
  if (!OUTFITS.includes(outfit)) throw new Error(`Unsupported outfit: ${character}/${outfit}`);
  const root = outfit === 'homewear' ? `/outfits/homewear/${character}` : `/${character}`;
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
