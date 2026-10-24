# Accepted office material response (issue #32)

The [owner accepted the paired comparison](https://github.com/rig-c/parts-examples/issues/32#issuecomment-6333270882) on 2026-10-22 after HQ reviewed the real-speed clips and contact sheets. The accepted comparison uses main `c239b09` as its before arm. This integration reproduces the accepted candidate outputs, not the old serving physics.

## Reconciled scope

| Target | Candidate change from current main |
| --- | --- |
| Hair and bangs on all five existing office characters | mass = 0.45; strength × 1.10; damping − 0.06; inertia × 0.85; wind × 1.40 |
| Jinni skirt only | mass = 0.70; strength × 0.75; damping + 0.02; inertia × 1.20; wind × 2.50 |

Values are authored profiles, rounded to six decimal places, not measured
material constants. The earlier candidate files and note identify Jinni's
skirt. The issue's phrase “second character” is not used to select a different
character. The other four lower-clothing profiles remain unchanged.

The five configs preserve current main's assembly plans, meshes, regions,
bones, motion, stops, every other constraint field, and the prior declared repairs. The `x-repairs` hashes now also bind the accepted material stage.
All accepted bust physics and topwear authoring settings remain unchanged.
Nova's accepted removal of cuff physics remains in its declared repair; this
candidate does not restore those constraints to the delivered rig.

The old Naru/Luna polygon substitutions are not reapplied over current main's
later accepted topwear corrections. Main's current topwear and repair payloads
are retained. Thus this candidate evaluates material response without a new
topwear remesh. The historical region proposals are superseded in this patch;
they have not been validated or accepted by omission. A new region proposal
would need a separate reviewed scope and source-feature/setup evidence.

The five historical upgrade scripts carry only matching material-profile
literal changes relative to their current-main versions. They remain historical
construction scripts, not a replacement for canonical configs plus declared
repairs, and must not be run wholesale over accepted outputs.

## Measurement contract

Use the existing pinned public tools: parts 1.25.0, rig-c 2.57.0 and official
Spine 4.3.13. Keep baseline and candidate motion, images, topology, weights,
anchors, stops, camera and sample times identical. No viewer/player/engine or
source-image change belongs to this candidate.

The [checker](tools/check-cloth-hair.ts) retains ordinary mode and adds
`--material-response`: idle at wind 0/1/3/4, phase-zero autoGust
`2*sin(2.2*t)+0.8*sin(5.1*t)`, and a moved packet (18, −10) at 0.5 seconds
with its inverse at 0.59 seconds. Each condition samples 0 through 12 seconds
at 60 Hz plus exact 0.59: 722 samples. Animation dt remains unchanged; physics
uses the existing `dt + dt*2^-30` clock. Both public core and official native
must agree for every bone and drawn vertex at tolerance zero.

Material mode refuses any authoring-rig change outside the exact profile fields
above. It also accepts an unchanged pair for controls. Only descendants and
weighted attachments of actually changed physics bones are exempted from the
protected calm comparison; all remaining geometry is still compared. Topwear
geometry and bust matrices must remain identical in every condition. Nova's
accepted cuff meshes have no live cuff physics: zero wind response is required
there, rather than treating absent response as a failed material improvement.

The report retains raw calm differences, support/root motion, folds, edge
ratios, wind traces and selected anchor-local moved-minus-idle traces. Material
summaries report first/opposite free extrema, half-cycle, zero crossings and
normalized versus shared-baseline absolute settling. A safety PASS does not
certify subjective lightness, realism or improvement. No exactly fixed support
vertices remains an explicit unmeasured state; weighted-root diagnostics are
reported separately.

Render the same native walk at 12 Hz: wind 0, wind 3 and jolt from 0 through
4 seconds; autoGust from 0 through 12 seconds. Both arms use full-body bounds
x = −400..400, y = 0..2284, height 800, and head bounds x = −250..250,
y = 1500..2284, scale 1. Keep the exact unanimated Physics.none setup captures.
These are controlled offline renders, not browser observations.

`--topwear-region-change` remains a separate component mode restricted to a
matching Naru or Luna pair. It reports cross-topology topwear comparisons as
not comparable and exits 2 even when its component checks pass. It is not used
for this same-topology candidate. `--equal-force-only` remains optional,
Jinni-only and diagnostic; it cannot replace actual-profile evidence.

## Declared reproduction and serving

Each office `declared-repairs.json` contains a `materialProfile` record: named
physics targets, the five old/new values, and complete raw/repaired rig hashes
for both arms. `config.json` binds the declaration with its existing `x-repairs`
SHA256. The stage verifies the accepted raw rig, reverses only those five values
to the previous repair preimage, applies every existing declared repair with
its original hashes, then applies and verifies the accepted profile. Nova's
full constraint-array check and removal of four cuff constraints remain intact.
An extra target, different coefficient, changed topwear, or other rig drift is
refused; there is no threshold or guard bypass.

The following paragraph records the original office-only acceptance. The later
uniform extension below supersedes only its uniform hair exclusion.

The three other outfits per character retain their previous office baseline
profile when merging common parts. The office-only acceptance does not retune
those fifteen outfits. Complete model and Spine equality remains required for
all twenty rigs; profiled office authoring bytes are checked too.

`out/rig/material-profile.provenance.json` records the profile, config,
authoring and compiled-model hashes and acceptance reference. Office serving
models, Spine files and check reports are the sealed accepted candidate's
outputs. The accepted-input manifest pins the refreshed artifacts; the ordinary
full reproduction and public compiler/check must reproduce them. Historical
repair provenance remains historical, with this later material stage explicit.

The accepted comparison's native/core parity, topwear and bust deltas and
candidate fold readings were zero for all five characters. Each before arm
also passed its unchanged-pair control. The comparison retained 31 planted
refusals, 5,850 original frames and 40 paired real-speed videos. These figures
refer to that frozen comparison, not to rerendering during integration.
Ordinary build/check still excludes live physics from its animation fold test;
Roa's missing eyewhite input remains an explicit blink SKIP. No new stress-force
or superseded polygon evaluation is claimed.

## Uniform shared-hair parity (issue #49)

The five uniform configs now state the accepted office hair and bang values for
the same 75 physics constraints: only `mass`, `strength`, `damping`, `inertia`
and `wind` change. Homewear and swimwear keep their previous physics. The
office-only skirt profile is not transferred, and no clothing, bust, bone,
motion, image, mesh, viewer or camera change belongs to this extension.

Each uniform declaration adds `uniformHairProfile`, with the accepted office
profile's SHA256, its complete hair target list and the whole repaired rig's
before/after hashes. The config must contain exactly those target values.
Existing assembly and repair preimages are checked first. The final uniform
stage changes only the five scalars, then checks the complete output hash;
reversing that stage must recover the accepted pre-extension rig. A missing
target, changed office profile, different coefficient or unrelated rig change
is refused. The older common-part merge remains unchanged for other outfits.

`out/rig/uniform-hair-profile.provenance.json` binds this profile, config,
authoring rig and compiled model. Ordinary reproduction must regenerate the
authoring and serving bytes with the pinned tools in the README.

### HQ switch acceptance and retained pixel residual

After viewing the [4x switch pair and diff overlay](docs/uniform-hair-switch.png),
HQ restated the #49 bar as exact posed coordinates of **every shared draw (73)**,
the viewed sheet with SHA256
`bd46337ef39f333d7e8a03818524dc8f4b4a562b31ceda35d415f07c621cd8c5`,
and the cold shared-atlas control at **0 pixels**. This ruling addresses the
hair-motion requirement: all shared coordinates agree while atlas UV sampling
and previous WebGL batch layout can change pixels for that same geometry.
The cold control uses identical static geometry and batch state, with office
shared textures/UVs substituted only in memory. It is a diagnostic control,
not a change to serving art, UVs or the renderer.

The original threshold-0 pixel gate remains honestly recorded: outside the
unchanged union of rendered neck alpha supports, the baseline was 53,272 pixels,
the Nova candidate was **358**, and a bounded local static replay was **357**.
The producer job exited **1** at its final `UNIFORM_CUT_BAR` assertion after
the five canonical builds and their physics allowlists passed. Its verified
serving outputs were retained and separately adopted under HQ's revised bar;
that historical job is not relabeled green. The original pixels are not claimed
zero. The residual belongs to [rig-c/play#187](https://github.com/rig-c/play/issues/187).
The local replay does not recover every original Nova pixel. No tolerance or
mask was enlarged, and the frame set was deleted after individual hashes and
the small sheet were retained. The diagnostic concatenated-PNG aggregate was
not computed before deletion; it is not inferred from individual hashes.

The [compact acceptance receipt](docs/uniform-hair-switch.json) binds source
digests, the sheet and the [exact shared-pose result](docs/uniform-shared-pose.json).
Reproduce the pose metric with the pinned viewer's actual parser, track and
posed-frame functions (1200 steps at 1/60, wind [4,0], gravity [0,0], identical
phase offsets and deterministic blink):

```bash
node family/tools/verify-uniform-hair.mjs --out .lane-evidence/new-uniform-pose.json
```

This compares all shared draws, including face and accessories, not just hair;
only clothing and the explicitly different neck plate are excluded. The adapter
refuses a viewer hash outside `accepted-inputs.json`. Tests plant coordinate,
topology, colour, order and missing/extra-draw defects, and separately reject
changes outside the exact physics allowlist. Same-input, planted-defect and
boundary controls precede the historical pixel metric.

Ordinary build/check still excludes live physics
from its animation fold test; no new stress-force, subjective material-quality
or physical-device acceptance is claimed.
