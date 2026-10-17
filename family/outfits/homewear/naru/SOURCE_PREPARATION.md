# Naru homewear source preparation

This folder prepares the fourth character from the user-selected homewear group
image for a separate outfit variant. It records the source preparation stage. The completed local variant and its
separate compiler, physics and browser evidence are described in [README.md](README.md).

`inputs/source-group.jpeg` is the unchanged 2752×1536 RGB source copy.
`source-provenance.json` records its SHA-256 and the provisional crop/resize.
The original download is never edited. Retaining the original group follows
the existing family example's practice of retaining its source group image;
this first prototype is a local demo; public publication is outside its scope.

The copied Naru crop is 538×1536. The installed RMBG-2.0 node produced a
nontrivial alpha mask, then the existing 4x-AnimeSharp model processed RGB and
the alpha repeated as RGB separately, taking the latter's red channel as alpha.
The 2152×6144 result was resized with LANCZOS to the existing 800×2284 rig canvas.
No painting retouch or hidden-surface invention was performed in this stage.
Model hashes, actual sizes and matting counts are in
`inputs/upscale-run/upscale.json`; measured CPU affinity/RSS are in its
`budget.json`. The raw 4x model output is retained alongside the registered image.

`docs/matte-upscale-contact.png` compares the original crop with the real result
on white and checker backgrounds. Alpha min/max and a nonempty box are guards
against the node's silent error fallback; they do not certify every strand or
slipper-edge pixel. Footwear versus floor-shadow ownership was subsequently checked against the
source in `docs/slipper-alpha-contact.png`: the sole is retained and the floor
reflection excluded.

The full-body input was created by the public `rig-parts inputs` command:
800×2284 painting, 2284×2284 input square, 742 pixels of white pad on either side.
`inputs/painting-clothing-source.png` is the explicit white composite used for
that command. It is not the final reference with the accepted face/hair restored.

`protected-baseline.json` hashes 45 accepted office authoring/image/model files.
`landmarks-draft.json` distinguishes existing authoring anchors from unmeasured
anatomical landmarks. Cyan crosses in the draft contact are those existing
anchors, not a new garment waistband or a measured registration verdict.

Run the portable preparation tools from the repository root:

```sh
python3 family/tools/homewear-naru-prepare.py --source /path/to/original-homewear.jpeg
python3 family/tools/homewear-naru-source-contact.py
# The GPU upscale tool is run only on the existing admitted Windows GPU box,
# with canonical installed model paths supplied as arguments; it installs nothing.
python3 family/tools/homewear-naru-matte-contact.py
python3 family/tools/homewear-naru-protected-check.py
```

Raw process logs stay in local execution evidence, outside the repository.
`runtime-evidence.json` retains their hashes. No host or user-machine address is
stored here. A failed See-through load is preserved separately as a resource
admission refusal; it is not a layer output. Subsequent garment splitting, neck/hand ownership, new geometry, approved
face/hair reuse, official build/check and live motion evidence are recorded in
`README.md`; the source-preparation hashes remain independently checkable.
