# Contributing

`rig-c/examples` holds the public input corpus that [`@rig-c/parts`](https://github.com/rig-c/parts) and [`@rig-c/play`](https://github.com/rig-c/play) fetch by pinned commit, standalone character samples (`rigboy/`), the five-character `family/` reference demo, and reproducibility trials (`trials/`).

## Getting the code running

The standalone corpus directories (`demo`, `wind`, `scarf`, `reference-demo`, `reference-sample`, `three-quarter`) are static input sets (painting, See-through inputs, and layer outputs). Consumers fetch them by commit SHA.

To run the interactive Family viewer locally from a clone (needs Node.js 22+ and Python 3):

```sh
node family/viewer/server.mjs
```

Open `http://localhost:4568` (or the port set by `PORT`) in a browser.

## Before you open a pull request

Every pull request must pass [`.github/workflows/hygiene.yml`](.github/workflows/hygiene.yml), which refuses committed local home directory paths in any tracked text file and checks top-level `README.md` against the repository's word cap, `##` heading allowlist, and dated-measurement rules (see [AGENTS.md](AGENTS.md)):

```sh
node scripts/check-readme.mjs
node --test scripts/check-readme.test.mjs
```

Run the fast Family input inventory and viewer/tool unit tests from [`.github/workflows/family-demo.yml`](.github/workflows/family-demo.yml):

```sh
node family/tools/verify-accepted.mjs --check-inputs
node --test family/tools/verify-accepted.test.mjs family/viewer/*.test.mjs
```

If your change touches `family/` or `.github/workflows/family-demo.yml`, install the pinned compiler and run the full reproducibility and acceptance rebuilds into a fresh directory outside the checkout (a long run that rebuilds all 20 character–outfit rigs and runs `rig-parts check`):

```sh
bun install --cwd family/tools/outline-field-islands --frozen-lockfile
bun family/tools/verify-reproducibility.mjs --out <repro-out-dir>
bun family/tools/verify-accepted.mjs --out <family-out-dir>
```

## Reporting a change

- **Issue first.** Open an issue before changing a sample, viewer, or trial. State the question, the inputs, the exact command, and the measured output.
- **One issue per pull request.** Keep each pull request scoped to a single issue.
- **Conventional Commits.** Write commit messages in English using [Conventional Commits](https://www.conventionalcommits.org/) with a scope (`feat(family):`, `fix(viewer):`, `docs(trials):`).
- **Public material only.** Do not include private names, unlicensed assets, or local machine paths. Trials live under `trials/<yyyy-mm-dd>-<slug>/` and never modify a corpus directory.

## Where further rules live

- [README.md](README.md) — repository layout, corpus structure, and model licence credits.
- [AGENTS.md](AGENTS.md) — top-level `README.md` word cap, `##` heading allowlist, and verification rules.
- [family/README.md](family/README.md) — Family pipeline, repair stages, and verification contracts.
- [trials/README.md](trials/README.md) and [trials/TEMPLATE.md](trials/TEMPLATE.md) — how trials are structured and recorded.
- [LICENSE](LICENSE) — MIT licence terms.
