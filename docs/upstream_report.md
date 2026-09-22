# Upstream Report Draft: Silent Acceptance of Type Mismatches Past the Relater Depth Fuse in typescript-go

*Prepared for filing at github.com/microsoft/typescript-go. All artifacts below are committed in this repository with executable reproducers.*

## Summary

`tsgo` **silently accepts** type-mismatched programs whenever the source↔target relation requires nesting deeper than 100 levels of type structure. No diagnostic is produced — not TS2322, not TS2321 — and the check returns exit code 0. `tsc` (5.9.3) reports `TS2321: Excessive stack depth comparing types` on the same input. An LSP session against `tsgo --lsp --stdio` likewise produces **zero diagnostics**, meaning the wrong code shows no red squiggle in an editor either.

This is a **regression vs. tsc** and a soundness hole: wrongly-typed programs compile clean.

## Root cause (mechanism-level)

Both implementations have the same fuse; they differ in what the fuse returns.

`tsc` (`typescript.js`, `recursiveTypeRelatedTo`):
```js
if (sourceDepth === 100 || targetDepth === 100) {
    overflow = true;
    return Ternary.False;
}
```
The caller (`checkTypeRelatedTo`) sees `overflow`, records `Failed | ComplexityOverflow` in the relation, and reports `Excessive_stack_depth_comparing_types` (TS2321). Verdict: **not related + loud**.

`tsgo` (`internal/checker/relater.go:3137`):
```go
// We stop relating if we reach 100 levels of nesting...
if len(r.sourceStack) == 100 || len(r.targetStack) == 100 {
    return TernaryMaybe
}
```
Two differences, both wrong:

1. **Wrong verdict.** `checkTypeRelatedToEx` ends with `return result != TernaryFalse` — `TernaryMaybe` therefore maps to **`true` (related)**, the opposite of tsc's `False`.
2. **Swallowed diagnostic.** No overflow flag is set and nothing is appended to `r.errorChain`, so neither of the two report paths in `checkTypeRelatedToEx` fires. The bail is completely invisible.

Result: `Maybe → success → rc=0, zero diagnostics` — silently accepted wrong code.

## Minimal reproducer

```ts
// deep.ts — mismatch nested at type depth 101+
type W<T> = { v: T };
type DeepA = W<W<W<...<W<string>>>>>;   // Array^101 of string-equivalent
type DeepB = W<W<W<...<W<number>>>>>;   // Array^101 of number-equivalent
declare const a: DeepA;
const b: DeepB = a;                     // SHOULD error; tsgo accepts silently
```

| checker | depth 100 | depth 101 | depth 150 |
|---|---|---|---|
| tsc 5.9.3 | TS2322 (correct) | **TS2321 (loud)** | TS2321 (loud) |
| tsgo (stock) | TS2322 (correct) | **silent accept** | silent accept |
| tsgo (fuse removed) | TS2322 | TS2322 at the leaf (correct) | TS2322 (correct) |

Boundary verified at exactly **type depth 101** (relater stack 100).

## Impact: the hole is reachable with realistic-looking code

The fuse counts *relation* depth, not source-level depth — no visibly pathological syntax is required. A generated typedef chain (as produced by OpenAPI/proto codegen or version-migration layers) suffices:

```ts
type Lib1Cfg0 = { endpoint: string };
type Lib1Cfg1 = { handler: Lib1Cfg0 };
// ...110 lines of {handler: Lib1CfgN}...
type Lib2Cfg0 = { endpoint: number };   // differs ONLY at the bottom leaf
// ...110 lines of {handler: Lib2CfgN}...
declare const theirs: Lib1Config;
const mine: Lib2Config = theirs;        // tsgo: CLEAN. tsc: TS2321. unfused: TS2322 at leaf.
```

Full file: `linux/probes/WEAPONIZED_REALISTIC.ts` (231 lines, all ordinary-looking type aliases + one assignment). To a human reader it looks like two library typings being combined — exactly what codegen/migration tooling produces.

## Scope of affected constructs (28 cases across 11 families)

Differential fuzzer (stock tsgo vs fuse-removed tsgo vs tsc 5.9.3) over 45 generated cases — `linux/run_silent_accept_v2.py` → `data/phaseXV_silent_accept_v2.json`:

**Silent accept (≥101 deep):** `Array<T>`, `Promise<T>`, tuples, `{v:…}` records, generic `Box<T>`, conditional types, generic inference return paths, class methods, getter return types, index signatures, class variance.

**Unaffected** (error correctly at any depth): contravariant function-argument positions, unions, `readonly T[]` — these traverse different relation code paths that never hit the fuse.

## Editor impact

`tsgo --lsp --stdio` (pull-diagnostics model): `textDocument/diagnostic` on a depth-150 mismatch file returns `items: []`. Control file (depth-10 mismatch) reports correctly; fuse-removed binary reports correctly on the deep file. Reproducer: `linux/run_lsp_probe.py` → `data/phaseXVI_lsp.json`. The silent accept is **user-visible in the editor**: no red squiggles.

## Fix cost is negligible

A rebuild with only `== 100` → `== 1000` at `relater.go:3137` reports honestly through depth 1000 then goes silent again at 1001 — the hole moves with the dial. Honest checking at depth 1000 costs 0.57s vs 0.55s unfused on these probes. Suggested upstream resolution: mirror tsc's behavior — set an overflow/failure marker + return `TernaryFalse`, or emit the same TS2321-style diagnostic and return `False`. Either is a few lines.

## Cross-language context

The same nested-mismatch probe on 11 production compilers (`linux/run_crosslang.py`, `linux/run_crosslang2.py` → `data/phaseXVII_crosslang.json`, `data/phaseXVIII_crosslang2.json`): **tsgo is the only silent acceptor.** rust, go, csc, swiftc, g++, clang++, ocaml, zig, ghc, f# all reject loudly. javac and kotlinc share a different failure mode (exponential time → internal exception); scalac stack-overflows in its parser. The conditional-10 Maybe sites at `relater.go:3576/3757` are present identically in tsc — shared upstream behavior, not this regression.

## Reproducibility

- Clone `ChloeVPin/project-chimera`, checkout tag `act-xviii`.
- `python3 linux/run_silent_accept_v2.py` — 45-case differential map.
- `python3 linux/run_lsp_probe.py` — real LSP session, depth-150 file → `items: []`.
- `python3 linux/run_price_of_correctness.py` — stock vs fuse-fixed vs fuse-removed cost table.
- tsgo binaries used: built from `microsoft/typescript-go` @ 89d5d5b2, `go build ./cmd/tsgo`.

## Generalization check — is the port faithful elsewhere?

Differential census of 1,044 cases (44 hand-targeted across 10 construct domains + 1,000 seeded random compositions, `linux/run_divergence_fuzzer.py` / `run_divergence_random.py` → `data/phaseXIX_divergence.json`): **zero verdict-level divergences** between tsc 5.9.3 and tsgo. The only diffs found are elaboration shape — on `Required<object>`/`Readonly<object>` (empty mapped type) assignment failures, tsc5 emits TS2740 ("missing properties …") while tsgo emits TS2322 with a differently-shaped chain. The silent accept is the anomaly, not the norm.

## Related observation — the fuse hides a quadratic, not a crash

On the fuse-removed build, deep check time scales O(depth²): ~9s at 20k, ~166s at 60k (identical types), >600s at 40k (mismatched). CPU profile shows the cost is **not** in the relation — it is `binder.NameResolver.Resolve` (35%), `getConditionalFlowTypeOfType` (38%), `isResolvedByTypeAlias` (19%) and `ast` ancestor walks: per-node work that traverses AST ancestors. Deep nominal types also produce zero additional instantiations. A fix for the silent accept would need the bail-out to be loud; the asymptotic bound is a separate (performance) consideration.

## Addendum (Act XX census) — two more silent-drop classes

**Post-fuse permissive-any suppression (affects tsc as well).** After the instantiation
fuse trips once (TS2589), the failed type becomes `errorType`, which is universally
assignable. Every subsequent relation involving that type silently passes. Repro:
```ts
type Bomb<T> = T extends any ? (Bomb<T> extends infer U ? [U,U,U,U,U] : never) : never;
const b = null as any as Bomb<Bomb<Bomb<Bomb<Bomb<string>>>>>;   // one TS2589
const wrong: { x: number } = b;                                   // silently accepted
```
Identical on tsc 5.9.3 and tsgo. This is arguably intended (errorType is meant to be
benign), but it means a single tripped fuse silently masks *all* further errors on that
type — worth noting since the same mechanism will hide the fix for the main defect if
it returns `errorType`.

**Config-gate asymmetry.** `tsgo file.ts` from a directory containing `tsconfig.json`
emits only TS5112 and returns `ExitStatusDiagnosticsPresent_OutputsSkipped` — the file
is never checked; every diagnostic in it is suppressed (`internal/execute/tsc.go:180-187`).
tsc 5.9.3 has no such gate: it checks the files but silently ignores the project config
(`strict:true` + file args → implicit-any file compiles rc=0). The strictness failure
mode is loud-exit/silent-check on tsgo vs silent-options on tsc; either way, a CI step
of the form `tsc changed-file.ts` quietly stops enforcing the project's real rules.

**Bail-site census (negative results are included for completeness).** Every
`TernaryMaybe` site was probed: `expandingFlags==Both` (relater.go:3162),
conditional-10 (3576/3757), union-include (1225/1232), cycle assumptions (3122/3130),
and the inference expanding-skip at depth 2 (inference.go:352/355, 1074/1077).
All are parity with tsc and, by construction, cannot hide a finite error — they fire
only on infinitely self-similar shapes where any real difference surfaces above the
trigger depth. `relater.go:3137` remains the only silent-accept regression in the port.

## Novelty claim (honest)

We are not aware of a prior public report characterizing this as a silent *accept* (wrong code compiles clean) rather than a missing-diagnostic nuisance, nor of the LSP-path demonstration or the cross-compiler uniqueness result. If a duplicate exists upstream, the reproducer corpus (45 generated cases + weaponized realistic case + LSP session) is still the artifact the maintainers would need.

*This report is a draft prepared for review; it has not been filed upstream.*
