# Upstream Report Draft: TypeScript 7 (native) silently accepts type mismatches past the relater depth fuse

*Prepared for filing at github.com/microsoft/TypeScript (the `typescript-go` staging repo is closed — the native port now lives in `tsc/` in the main repo). All artifacts below are committed in this repository with executable reproducers.*

## Search terms used (per the bug template)

`Excessive stack depth comparing types`, `TS2321`, `deeply nested assignable`, `silent accept`, `missing diagnostic`, `TernaryMaybe`, `relater`, `type error not reported`. Closest hit is #63887 ("textDocument/diagnostic on the first-opened file can silently omit real errors") — an unrelated mechanism (fresh-session pull diagnostics, not relation depth). No prior report of this regression found in microsoft/TypeScript or the archived typescript-go tracker.

## Version & regression information

- **Affected:** TypeScript 7.1.0-dev (current main, e.g. `typescript@next` = 7.1.0-dev.20260922.1 — the bug is in today's nightly and every nightly since the merge).
- **Not affected:** `@typescript/native-preview` 7.0.0-dev.20260707.2 and all earlier previews — they emit TS2321 correctly. The npm preview channel stopped publishing 2026-07-07, which brackets the regression.
- **Not affected:** tsc 5.x (JS build) — emits `TS2321: Excessive stack depth comparing types` loudly, as it always has.
- **Introduced by:** `microsoft/typescript-go` PR **#4913** ("Improve recursion identities and `isDeeplyNestedType`", commit `12548e2a1`, merged 2026-08-18), which changed the depth-100 bail in `recursiveTypeRelatedTo` from `r.overflow = true; return TernaryFalse` to `return TernaryMaybe`.

## Summary

`tsc` (native) **silently accepts** type-mismatched programs whenever the source↔target relation requires nesting deeper than 100 levels of type structure. No diagnostic is produced — not TS2322, not TS2321 — and the check exits 0. The JS implementation reports `TS2321` on the same input; so did the native preview builds from before the change.

This is a soundness hole in the new checker: wrongly-typed programs compile clean, with no error in the CLI or the language server.

## Root cause (mechanism-level)

`tsc/internal/checker/relater.go:3133`:

```go
if len(r.sourceStack) == 100 || len(r.targetStack) == 100 {
    // We stop relating if we reach 100 levels of nesting...
    return TernaryMaybe
}
```

`checkTypeRelatedToEx` ends with `return result != TernaryFalse` (relater.go:397), so `TernaryMaybe` maps to **`true` (related)** — the opposite of the pre-#4913 `TernaryFalse`. No `r.overflow` flag is set and nothing reaches `r.errorChain`, so the bail is completely invisible.

The intent of #4913 was clearly good: it eliminated false-positive TS2321 reports on infinitely-recursive-but-fine types (typescript-go #4807, #4465, #1730 were all "false excessive-depth error" complaints; the PR removed a stale 8-error baseline for `excessivelyDeepConditionalTypes`). The side effect is that the bail now also silences *genuine* mismatches. The loud-bail machinery (`r.overflow`, `RelationComparisonResultOverflow`) is intact and still used by the other fuse one line away (`if r.relationCount <= 0 { r.overflow = true; return TernaryFalse }`) — only this bail went quiet.

## Minimal reproducer

```ts
// deep.ts — mismatch nested 101 levels deep
type W<T> = { v: T };
type A = W<W<W<...<W<string>>>>>;   // W^101
type B = W<W<W<...<W<number>>>>>;   // W^101
declare const a: A;
const b: B = a;                     // SHOULD error
```

Verified today on three builds:

| checker | depth 100 | depth 101 | depth 150 |
|---|---|---|---|
| tsc 5.9.3 | TS2322 (correct) | **TS2321 (loud)** | TS2321 (loud) |
| typescript@next 7.1.0-dev | TS2322 (correct) | **silent accept, rc=0** | silent accept, rc=0 |
| typescript-go head w/ bail restored to `overflow+False` | TS2322 | TS2322 at leaf (correct) | TS2322 (correct) |

Playground link can't demonstrate this — the Playground runs the JS tsc, which is unaffected. Repro is 5 lines + `npm i typescript@next && npx tsc --noEmit deep.ts`.

## Impact: reachable with realistic-looking code

The fuse counts *relation* depth, not source depth — no pathological syntax required. A generated typedef chain (what OpenAPI/proto codegen or versioned-config typings look like) suffices:

```ts
type Lib1Cfg0 = { endpoint: string };
type Lib1Cfg1 = { handler: Lib1Cfg0 };
// ...110 lines of {handler: Lib1CfgN}...
type Lib2Cfg0 = { endpoint: number };   // differs ONLY at the bottom leaf
// ...110 lines of {handler: Lib2CfgN}...
declare const theirs: Lib1Config;
const mine: Lib2Config = theirs;        // 7.1.0-dev: CLEAN. 5.x: TS2321.
```

Full file: `linux/probes/WEAPONIZED_REALISTIC.ts` (231 lines of ordinary-looking aliases + one assignment).

## Scope of affected constructs (28 cases across 11 families)

Differential fuzzer (stock vs fuse-restored build vs tsc 5.9.3) over 45 generated cases — `linux/run_silent_accept_v2.py` → `data/phaseXV_silent_accept_v2.json`:

- **Silent accept (≥101 deep):** `Array<T>`, `Promise<T>`, tuples, `{v:…}` records, generic `Box<T>`, conditional types, generic inference return paths, class methods, getter return types, index signatures, class variance.
- **Unaffected** (error correctly at any depth): contravariant function-argument positions, unions, `readonly T[]` — different relation code paths that never reach this bail.

## Editor impact

`tsc --lsp --stdio` (pull-diagnostics model): `textDocument/diagnostic` on a depth-150 mismatch file returns `items: []` — no squiggle. Controls report correctly. Reproducer: `linux/run_lsp_probe.py` → `data/phaseXVI_lsp.json`. (Verified on typescript-go @ 89d5d5b2; the mechanism is the same `checkTypeRelatedToEx` path and the CLI hole reproduces identically on current main.)

## Suggested fix

Restore the pre-#4913 shape — `r.overflow = true; return TernaryFalse` — or equivalently mark the bail as an overflow and surface a diagnostic (a gentler variant could keep #4913's false-positive fix while reporting only when the fuse trips *during a mismatch elaboration* — the maintainers will know the right cut). The `overflow` machinery is untouched and still wired to `RelationComparisonResultOverflow` reporting.

A caution that affects whatever fix is chosen: after the instantiation fuse trips (TS2589), the failed type becomes `errorType`, which is universally assignable and silently passes subsequent relations — so if the fix routes through `errorType`, it will mask the very diagnostics it restores. (Observed identically in 5.x and native; noted only as a fix-design constraint, and arguably intended cascading-error suppression.)

## Generalization check — the port is otherwise faithful

Differential census of 1,044 cases (44 hand-targeted across 10 construct domains + 1,000 seeded random compositions; `linux/run_divergence_fuzzer.py` / `run_divergence_random.py` → `data/phaseXIX_divergence.json`): **zero verdict-level divergences** between tsc 5.9.3 and native. The only diffs are error-elaboration shape on `Required<object>`/`Readonly<object>` assignment failures. This silent accept is the anomaly, not the norm.

## Cross-language context

The same nested-mismatch probe across 11 production compilers (`linux/run_crosslang.py`, `run_crosslang2.py` → `data/phaseXVII_crosslang.json`, `phaseXVIII_crosslang2.json`): rustc, go, csc, swiftc, g++, clang++, ocaml, zig, ghc, f# all reject loudly; javac/kotlinc degrade to exponential-time hangs; scalac overflows its parser. The native tsc is the only silent acceptor — and only since #4913.

## Reproducibility

- Clone `ChloeVPin/project-chimera` (research repo; all runners committed under `linux/`, artifacts under `data/`).
- `python3 linux/run_silent_accept_v2.py` — 45-case differential map.
- `python3 linux/run_lsp_probe.py` — LSP session → `items: []` on the deep file.
- `python3 linux/run_whisperer_census.py` — full bail-site census (negative results included: every other `TernaryMaybe` site was probed and is parity with the JS implementation or structurally incapable of hiding a finite error).
- Binaries: typescript-go @ 89d5d5b2 (closure commit), `tsc` built from microsoft/TypeScript main (7.1.0-dev), `typescript@next`, `@typescript/native-preview` 7.0.0-dev.20260707.2, tsc 5.9.3.

## Notes for the maintainers (related observations, not defect claims)

- `tsc file.ts` in a directory containing `tsconfig.json`: tsc 5.x checks the file and ignores the project config — [documented behavior](https://www.typescriptlang.org/docs/handbook/tsconfig-json.html) — while 7.x emits TS5112 and skips checking entirely. Deliberate on both sides; we note it only because "check one changed file" CI steps behave oppositely across versions and the silent-config-ignore direction on 5.x surprised users historically.
- Deep-check cost on the bail-free build scales O(depth²) driven by `NameResolver.Resolve`/`getConditionalFlowTypeOfType`/`isResolvedByTypeAlias` ancestor walks (same asymptotics in the JS implementation) — context for why the fuse exists; not a request.

## Novelty claim (honest)

We are not aware of a prior report of this regression. It is 5 weeks old at time of writing (introduced 2026-08-18, in the gap between the last native-preview build and the monorepo merge), so the window where a report could exist is short. The artifact set above stands on its own if a duplicate exists.

*FILED as [microsoft/TypeScript#64390](https://github.com/microsoft/TypeScript/issues/64390) on 2026-09-22 by the repository owner, with AI-assistance disclosure as the first line. Research conducted by an AI agent (Devin) under human direction.*
