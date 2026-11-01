# AGENTS.md

Instructions for agents working in `@rig-c/examples`.

## README rule

> **`README.md` is the front door for a visitor who just arrived. It answers four questions — what this is, why to care, how to use it in 60 seconds, and where to go next — and then stops. Everything else (flag tables, JSON schemas, architecture internals, edge-case rules, benchmarks, verification receipts, release checklists, paper citations, design history) lives in `docs/` or code comments and is linked in one line. A PR that adds a feature does not add a README section; at most it updates one row of the link table.**

In `rig-c/examples`:

- Keep `README.md` at or below `README_WORD_CAP = 2350` whitespace-delimited words (`ceil(2130 * 1.10 / 50) * 50`, measured after `#81`).
- Keep `##` headings strictly on the allowlist enforced by `scripts/check-readme.mjs`:
  - `Family: repairing the result`
  - `Trials`
  - `Layout`
  - `How they were made`
  - `Terms`
  - `How rig-parts fetches this`
- Do not paste verbatim prompts, per-character painting recipes, or dated measurement logs (`measured on 20…`, `read on 20…`, or `YYYY-MM-DD` inside a Markdown table cell) into `README.md`.
- Put per-character generation provenance and prompts in `<key>/generation.json`, candidate screening tables in `<key>/candidates.json`, See-through run records in `<key>/layers/{full,head}/meta.json`, standalone sample details in `<key>/README.md` (with at most one index line in `README.md`), and trial records in `trials/<yyyy-mm-dd>-<slug>/README.md`.

## Verification

Run the README check and its planted-failure unit tests before opening or updating a PR:

```sh
node scripts/check-readme.mjs
node --test scripts/check-readme.test.mjs
```
