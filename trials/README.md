# Trials

A trial is a record of something tried with the rig-c toolchain
(`@rig-c/core`, `@rig-c/parts`, `@rig-c/play`) to answer one question: *does
this work?* It is kept whether the answer was yes or no. A failed trial is as
much a deliverable as a passing one: it is what stops the next attempt from
repeating it.

Write a trial for a reader who was not there. That reader has this directory
and nothing else — no conversation, no issue thread, no memory of the session
that ran it. Anything settled elsewhere and not written here did not happen.
The [Family case study](../family/REPAIR_CASE_STUDY.md) is the model to read
first: it records rejected fixes, measured conditions and remaining limits
beside the result.

## The one rule

🔒 **A trial never edits a corpus directory.** The corpus is `demo/`,
`wind/`, `scarf/`, `reference-demo/`, `reference-sample/`, `three-quarter/`
and `family/`. Consumers fetch it by pinned commit, so a change there is a
change every consumer has to re-pin to, and it is made on its own, never as a
side effect of a trial. A trial *reads* the corpus: name the directory and the
commit it was read at, and write every output inside the trial's own
directory.

## Where a trial goes

One directory per trial:

```
trials/<yyyy-mm-dd>-<slug>/
  README.md        the record — required, in the order below
  <small evidence> JSON, scripts, contact sheets (see "What goes in")
```

- `<yyyy-mm-dd>` is the day the measurement was run, not the day it was
  written up.
- `<slug>` is lowercase words joined by hyphens and names the question, not
  the outcome (`walk-retarget-from-pose`, not `walk-works`).
- A trial run again later is a new directory with its own date. Do not
  rewrite an old trial's verdict; a new trial that contradicts it links back
  to it, and the old one gains one line at the top pointing forward.

## What goes in

- The README, every time.
- Data the trial produced or consumed that is small and that this repository
  may publish: JSON (measurements, cleaned poses, configs), the script that
  ran the measurement, contact sheets and still images under about 1 MB each.
- Generated inputs, with the record that generates them again (checkpoint,
  sampler, seed, prompt, graph).

## What stays out

- **Third-party video, art or other material.** A reference video stays out;
  only the processed data derived from it (for example a cleaned pose) goes
  in, and the README says what was withheld and where it came from.
- **Large renders and videos.** Commit their SHA-256 and the command that
  reproduces them instead.
- **A licence review of its own.** Licensing is settled once, on the rig-c
  [licensing page](https://rig-c.github.io/docs/licensing/) and on each
  input's own page, not per trial. A trial names where each input came from
  and stops there. When a file's standing is unclear, it is not argued about
  here: commit its SHA-256 and the command that reproduces it, and move on.
- **Local paths and private names.** No home-directory path, machine name or
  account, and no name of a project, character or corpus outside this
  repository's public examples.
- **Edits to a corpus directory** — see the one rule.

## The README

The README carries these sections, in this order, and none is left out. A
section with nothing to say states that, in a sentence.

1. **Question** — one question with a yes, no or partly answer, naming the
   tool and the behaviour.
2. **Inputs** — each input and where it came from (corpus directory and
   commit, URL, or the generating command). Origin, not a licence review: the
   licensing page covers that. Then what was withheld, and why. Pose/video
   trials complete the acquisition checklist below, including camera evidence
   and the accepted-sequence control, or state why it does not apply.
3. **Commands and pins** — every command exactly as run, in order, and the
   exact version or commit of every tool, checkpoint and model it used.
   "Latest" is not a pin. Include acquisition, pelvis before clean when
   applicable, the drawing-specific clean flags and their reasons, and the
   matched-control decision before downstream commands.
4. **Measurement** — figures, not adjectives: the quantity, its value, the
   threshold it is judged against, and the output it was read from. State the
   threshold *before* measuring; a bar fitted to the result is not a bar. For
   every render or video not committed, its SHA-256 and the command that
   reproduces it. A new acquisition of a clip with an accepted sequence needs
   a per-joint matched comparison and its verdict before downstream work.
5. **Verdict** — **PASS**, **FAIL** or **PARTIAL**, with the figure that
   decides it. A failure is stated as plainly as a success. PARTIAL names
   which part passed and which did not.
6. **Rejected alternatives** — what else was tried or considered, and why it
   was rejected, with its figure or observation.
7. **Limits** — what the trial does not show: how many inputs it covers,
   what was judged by eye, which conditions were not measured.

Mark a figure that was estimated rather than measured as an estimate, and say
who or what estimated it. A figure that is not known is written as not known.

## Acquisition checklist for pose/video trials

Record the detector/extractor name and exact version or commit, extraction
command/settings, model/checkpoint and weights SHA-256. Pin the clip interval,
person, timestamps/fps, crop and image dimensions as well as the output
sequence. A pose-tool pin alone does not identify the model that acquired it.

**Camera is part of acquisition.** State whether the shot zooms or pans. If
it does, keep how the track was made: tracking settings or hand-key file and
hash, key count and frame/value list, interpolation command, and measured
scale/translation ranges. The output sequence carries per-frame `camera`
entries (`s`, `tx`, `ty`, `inliers`) and a `cameraSource` description. Its
joints are already normalized to frame 0 by `(p - t) / s`; preserve that
contract through pelvis, clean and comparison. If it does not move, write
"static shot, measured: scale drift X %", report pan drift in pixels, and
name the measurement command/output. Absence of a camera track is not a
measurement of a static shot.

**Read the drawing before choosing preparation.** When it has a
waistband/skirt, run `rig-pose pelvis --mode waistband` before `rig-pose clean`
and record the frame inputs, read/declined frames and `pelvisSource`. The
reader needs one PNG per sequence frame in filename order at the sequence's
image dimensions; a declined frame stays explicit. State why a pelvis stage
does not apply when omitting it. Use clean's `--hips-inferred` when a
skirt/cloak hides the hips and explain why; it marks their state, not a
position correction or a substitute for pelvis. Use `--loop` for one cycle
and state its matching boundaries; it wraps the windows, re-pins the floor
and writes `travel: "in-place"`. State why either flag is absent as explicitly
as why it is present. The template supplies a conditional command example;
each trial records only the commands and flags it actually used.

**Use the accepted acquisition as a matched control.** Before any downstream
retarget, build or authoring from a new acquisition, check whether this clip
already has an accepted sequence. Pin it by path and commit/hash, then compare
per joint using a pinned comparison script/command. Match the person, clip
interval, frame times, image dimensions, coordinate space and preparation
stage; declare resampling. Compare the same camera-normalized space, with
raw-image readings reported separately when available. Record per-joint RMS,
maximum error and worst frame in pixels, compared/missing/inferred frame
counts and the exclusion policy. Fix the acceptance thresholds before the
measurement, and resolve a regression or reject the new acquisition before
downstream work; do not build on a rejected acquisition. A pooled score cannot
replace the per-joint record. If no accepted sequence exists, record where
checked and say so; do not claim a matched pass.

## Template

Start from [TEMPLATE.md](TEMPLATE.md), which carries the same skeleton with a
prompt in each section:

```bash
mkdir trials/<yyyy-mm-dd>-<slug>
cp trials/TEMPLATE.md trials/<yyyy-mm-dd>-<slug>/README.md
```

The skeleton, for reference:

```markdown
# <yyyy-mm-dd> <slug>: <the question, in a few words>

## Question

## Inputs

| Input | Where it came from | Origin | Committed here? |
| --- | --- | --- | --- |

Withheld:

## Commands and pins

| Tool | Version or commit |
| --- | --- |

## Measurement

| Measured | Value | Threshold | Source |
| --- | --- | --- | --- |

Renders and videos not committed:

| File | SHA-256 | Reproduced by |
| --- | --- | --- |

## Verdict

**<PASS | FAIL | PARTIAL>** —

## Rejected alternatives

## Limits
```
