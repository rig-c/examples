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
- **Anything that cannot be released under this repository's
  [LICENSE](../LICENSE).** That licence covers the images and JSON here; a
  file that may not be released under it is withheld and listed as withheld.
- **Local paths and private names.** No home-directory path, machine name or
  account, and no name of a project, character or corpus outside this
  repository's public examples.
- **Edits to a corpus directory** — see the one rule.

## The README

The README carries these sections, in this order, and none is left out. A
section with nothing to say states that, in a sentence.

1. **Question** — one question with a yes, no or partly answer, naming the
   tool and the behaviour.
2. **Inputs** — each input, where it came from (corpus directory and commit,
   URL, or the generating command), and its licence or the statement that it
   was generated. Then what was withheld, and why.
3. **Commands and pins** — every command exactly as run, in order, and the
   exact version or commit of every tool, checkpoint and model it used.
   "Latest" is not a pin.
4. **Measurement** — figures, not adjectives: the quantity, its value, the
   threshold it is judged against, and the output it was read from. State the
   threshold *before* measuring; a bar fitted to the result is not a bar. For
   every render or video not committed, its SHA-256 and the command that
   reproduces it.
5. **Verdict** — **PASS**, **FAIL** or **PARTIAL**, with the figure that
   decides it. A failure is stated as plainly as a success. PARTIAL names
   which part passed and which did not.
6. **Rejected alternatives** — what else was tried or considered, and why it
   was rejected, with its figure or observation.
7. **Limits** — what the trial does not show: how many inputs it covers,
   what was judged by eye, which conditions were not measured.

Mark a figure that was estimated rather than measured as an estimate, and say
who or what estimated it. A figure that is not known is written as not known.

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

| Input | Where it came from | Licence or origin | Committed here? |
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
