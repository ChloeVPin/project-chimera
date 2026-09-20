---
name: testing-project-chimera
description: How to run and end-to-end test the Project Chimera research codebase (Node CLI, C harnesses, static Canvas dashboards) on this Linux box
---

# Testing Project Chimera

Research repo: Node CLI `bin/chimera.js`, C litmus/IPC harnesses under `linux/` + `apple_silicon/`, Python runners, and zero-dependency static dashboards in `visualizer/` (mirrored byte-identical in `docs/` for GitHub Pages).

## Environment

- Node 22.20 + npm/npx live at `~/tools/node/bin` — **export first**: `export PATH=$HOME/tools/node/bin:$PATH`
- `npm test` = `npx tsc --noEmit` over `src/**` (tsconfig strict; `linux/probes/*.ts` is NOT typechecked — outside tsconfig include).
- Toolchain present: gcc/cc 11.4, clang++ 14, rustc 1.97.1, python3.10 + numpy + scipy, `/usr/bin/time -v`, wmctrl/xdotool, Chrome for Testing at `~/.local/bin/google-chrome` (DISPLAY :0 already up).

## CLI subcommands

- `node bin/chimera.js report` — scorecard (exit 0).
- `node bin/chimera.js litmus` — on Linux compiles `linux/litmus/litmus_test.c` via `cc -O2 -pthread` **only if the binary is absent** (it is a gitignored build artifact — delete `linux/litmus/litmus_test` to exercise the compile path); runs 500k iters → `data/phaseL4_linux_litmus_results.json`. Expect SB RELAXED violations >0, everything else 0. Expect `-Wformat` %llu warnings on LP64 (harmless).
- `node bin/chimera.js linux` (alias `probe`) — full Act V suite: L1 fuse probes (~20 npx-tsc invocations, ~75 s, FREEZE cases ~13 s each), L3 quad-compiler bench, L5 hydra fuzzer (writes `crashes/linux/*`), L6 core ping-pong. Total ~2.5 min — run backgrounded.
- **Side effects:** `litmus`/`linux` overwrite committed `data/phaseL*.json` and `crashes/linux/*_info.json` with fresh empirical values; `L3`/`L5` may touch `rust_chimera/target/.rustc_info.json`. After testing restore with `git checkout -- data/ crashes/linux/ rust_chimera/target/` to keep the tree clean.

## Dashboards

- Serve repo root: `python3 -m http.server 8000`, open `visualizer/index.html`, `visualizer/riemann.html`, `docs/index.html`.
- Data is **embedded** via `<script src="data_bundle.js">` → `window.CHIMERA_DATA` / `window.RIEMANN_DATA` — no fetch()/backend; even file:// works. Zero console errors expected.
- index.html: Rule 110 canvas (#caCanvas, `▶ Animate` button), tabs tab-triad/tab-typescript/tab-pathological; tables `#triadTableBody`/`#trampolineTableBody` are JS-populated.
- riemann.html: canvases tapeCanvas/chartR2/chartPs/chartDelta3 draw on `load`; spectrum pan slider triggers live redraw.

## Gotchas observed

- `browser_console` evaluates JS against the **first Chrome window** — close any extra "New Tab" windows (`wmctrl -l` / `wmctrl -i -c <id>`) or evals silently hit chrome://new-tab-page.
- Pre-existing bug: `data_bundle.js` stores Phase-5 data under `logarithmic_horizons`, but `initTrampolineTable()` reads `.results` → trampoline table renders empty. Not PR-related.
- JSON metadata hardcodes `"cpu": "Apple M2"` and report text is macOS-flavored even on x86 Linux — cosmetic only.

## Devin Secrets Needed

None — all testing is local and unauthenticated.
