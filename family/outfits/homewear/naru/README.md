# Naru homewear prototype

The local family viewer can replace Naru's office model with this homewear model.
The other four characters retain their accepted office assets. This first
prototype is a local demo; public publication is outside its scope.

The variant keeps the accepted 800×2284 stage, all 69 existing bones in their
original order and setup, all 29 existing constraints and stops, the exact idle
motion file, and the exact 15 face/hair attachments and PNGs. It appends two
cardigan hem bones with separate physics. `out/rig/rig.json` is the consumer rig
specification; `out/check/build/` is its ordinary gated serving closure.

## Source and ownership

The original source copy and registration are recorded in
`source-provenance.json` and `SOURCE_PREPARATION.md`. The source was matted with
the installed RMBG-2.0 model, upscaled through the existing AnimeSharp RGB/alpha
pipeline, and registered to the accepted stage. It was not painted over.

The installed See-through v3 node ran its unchanged body and internal head
passes at 1024, seed 42, 30 steps. Its actual output is 24 raw layers and 25
postprocessed parts, not an assumed older layer count. The original loader
expanded stored BF16 weights to FP32 before its final BF16 cast and exceeded
the admitted 24 GiB budget. The bounded successful invocation initialized the
same installed classes/checkpoints directly in BF16. Pipeline group offload is
unavailable in the installed version and was not active. No server, shared node
or model directory was changed.

| Final part | Actual material | Binding |
| --- | --- | --- |
| neck | source visible skin and generated hidden neck | head/chest; lower seam shares chest |
| topwear | camisole and exposed chest from `topwear` | existing chest/hip and bust field |
| cardigan | torso cardigan from `topwear` | chest/hip plus two new hem bones |
| sleeves | sleeve portion of `handwear-l` | chest only |
| hands | clasped hands split from `handwear-l` | separate foreground chest slot |
| bottomwear | trousers from `legwear`, visible source folds restored | rigid hip |
| shoes | original visible ankles/slippers; no floor reflection | rigid root |

The model's `bottomwear`, `footwear`, `handwear-r` and several accessory tags
contained sparse noise, not useful extracted garments. They were not relabelled
as successful clothing. Generated head/hair outputs are unused. The trousers do
not use the old skirt chains; the preserved skirt constraints have no new-cloth
weights. Hands and sleeves have no bust or hem influence.

`prepared-base/` records the source-projected parts before the narrow repair.
`prepared/` records the final parts. Original visible waist, drawstring, folds,
slippers and outer garment contours use registered high-resolution source pixels.
The explicit source-space cuts and edge treatment are in their `prototype.json`.

The shorter accepted hairstyle exposed a generated pale strip and an accidental
imprint of the source hairstyle. One built-in image generation edit repaired
only this hidden neck/upper-cloth material. `hidden-repair/` retains its input
references, raw output, prompt, fixed 2244-pixel consumer mask and admission
proof. These are generated hidden pixels, not recovered source pixels. Every
RGBA pixel outside that mask is identical to the preimage; the original source
and accepted face/hair are unchanged. See `docs/hidden-repair-mask-contact.png`.

The first moving composition also exposed a horizontal skin seam. Its lower
neck vertices and upper camisole/cardigan vertices now reuse the same existing
chest bind frame. This changes only new clothing weights; all common solver
coefficients and animation remain unchanged. `out/neck-seam-stitch.json` records
the affected vertices. `docs/neck-motion-before-after.png` shows both versions
at the same original idle phases, 1.0 and 2.5 seconds.

## Validation

The pinned public tools are parts 1.25.0, rig-c 2.57.0 and official Spine 4.3.13.
The ordinary public rig stage, official packed build, and full parts check pass.
The final parts check reports seam mean 0.142, 30 pixels over 40, loop delta 0 and
no undeclared animation folds. Its ordinary fold check excludes 31 physics
constraints; it is not the live-physics proof.

The parts-check PASS includes explicit SKIPs. `BREATH_VISIBLE` and
`TIP_OVER_ROOT` have no matching original See-through semantic tag in these
custom authored part records; neither bar is claimed as measured.
`RECOMPOSITE_HOLES` skips because this parts manifest has no `recomposite` block.
`STILL_REGIONS_DARK` measures the face but leaves feet unmeasured because no
part retains a See-through `footwear` tag. The source contacts, browser review
and separate numerical physics measurements remain distinct evidence; they do
not turn these skipped semantic bars into passes.

`runtime/physics.json` measures 721 poses at 60 Hz for each of calm, constant
wind 4, the viewer's breeze, positive single 2.4-second gusts of 48 and 96, and a
public physics jolt `(18,-10)` at 2 seconds with its return at 2.1 seconds. The
viewer wind adapter is imported directly. The jolt's 90 ms UI return is sampled
at the following 60 Hz frame, 100 ms. Gravity is zero. These are fixed-step
geometry measurements, not performance measurements or browser captures.

Every case has exact official/core pose parity, exact common-bone and unchanged
face/hair vertex identity against office, exact bust-bone identity and zero new
mesh fold readings. Hands, sleeves and trousers have zero wind/jolt-only motion.
New cardigan weights and physics give a different cloth response: this is not a
claim that different garments have identical deformation.

The final browser evidence is separate: `docs/browser-naru-homewear.png` and
`docs/browser-family-homewear.png`. It covers the actual viewer variant switch
and visible composition. `validation-runs.json`, `serving-independent-proof.json`
and `completion-control.json` retain the measured compiler, resource, identity
and missing-variant boundaries. Raw runner logs and full frame sequences stay in
sealed local evidence, not this repository.

The existing office CI verifier excludes this outfit directory. Its green
result does not certify homewear. The scoped reproduction below is currently a
separate verification step, not an installed CI job. Negative winds, arbitrary
drag paths and a general wardrobe/character authoring system are outside the
six measured physics cases.

## Reproduce

From the repository root, the read-only completion check must find the variant:

```sh
python3 family/tools/homewear-naru-protected-check.py --require-variant
```

Run the scoped verification through the configured pooled runner. It performs
its frozen install under an inherited four-CPU, aggregate 4 GiB process-tree
guard, then builds/checks into fresh evidence, compares the complete serving
inventory, exact non-PNG bytes and decoded PNG RGBA, and repeats the six physics
cases. Comparator controls refuse changed model bytes, changed pixels and
extra/missing serving files.

```sh
nova-run.sh --label "Naru homewear reproduction" --owner "Codex" \
  --session "$CODEX_THREAD_ID" --install '' -- \
  python3 family/tools/homewear-naru-guard.py --verify-only
```

For reauthoring, use a fresh isolated copy with only generated `prepared-base/`,
`prepared/`, `authoring/` and `out/` removed from that copy. Preserve the retained
source, layers, fixed repair mask and raw generated patch. Preparation requires
Python with Pillow, NumPy and SciPy; the measured preparation environment was
Python 3.13.1, Pillow 12.2.0, NumPy 2.4.4 and SciPy 1.17.1.

```sh
python3 family/tools/homewear-naru-static.py
python3 family/tools/homewear-naru-repair-composite.py
python3 family/tools/homewear-naru-author-inputs.py
nova-run.sh --label "Naru homewear authoring" --owner "Codex" \
  --session "$CODEX_THREAD_ID" --install '' -- \
  python3 family/tools/homewear-naru-guard.py --final-check
```

These steps reuse the saved generated patch; they do not rerun image generation
or claim that a fresh generative model call will be bit-identical. Normal
compiler validation is always retained. The `painting.png` reference is the
intended registered composition with accepted head and new clothes, so its seam
check alone is not an independent source-fidelity oracle. The original crop and
source contacts provide that separate visual comparison.
