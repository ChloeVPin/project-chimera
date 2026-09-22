# Draft issue; for filing at github.com/microsoft/TypeScript (bug_report template)

*Each section maps to a field in their bug report form. AI disclosure is the first
paragraph of "Additional information" per the user's ask and the repo's AI policy.*

---

## TITLE

TypeScript 7 (native) silently accepts mismatched types past the relater depth fuse (typescript-go#4913)

## 🔎 Search Terms

`TS2321`, `Excessive stack depth comparing types`, `deeply nested`, `silent accept`,
`no error reported`, `assignable`, `relater`, `TernaryMaybe`, `typescript-go`, `native preview`

## 🕗 Version & Regression Information

- Affected: `typescript@next` (verified on 7.1.0-dev.20260922.1; the nightly channel
  now ships the native compiler) and a from-source build of `main`.
- NOT affected: `@typescript/native-preview` 7.0.0-dev.20260707.2 and all earlier
  previews (emit TS2321 correctly; preview publishing stopped 2026-07-07).
- NOT affected: `typescript@5.9.3` (emits TS2321 loudly, as it always has).
- Changed in commit: [typescript-go#4913](https://github.com/microsoft/typescript-go/pull/4913)
  ("Improve recursion identities and `isDeeplyNestedType`", 12548e2a1, merged
  2026-08-18). Per its own description it "removes the excessive stack depth
  relation error" (fixes #4807); in `recursiveTypeRelatedTo` the depth-100 bail
  changed from `r.overflow = true; return TernaryFalse` to `return TernaryMaybe`.

## ⏯ Playground Link

(none; the Playground runs the JS checker, which is unaffected. Repro is 6 lines below.)

## 💻 Code

```ts
type W<T> = { v: T };
type A = W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<string>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>;
type B = W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<W<number>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>;
declare const a: A;
const b: B = a;
```

(The nesting must be literal: generator `'W<'*N + 'string' + '>'*N`, likewise
`'number'`. N=101 shown; N=100 still errors correctly; the bail trips at a
relation stack of 100.)

## 🙁 Actual behavior

`tsc --noEmit` exits 0 with zero diagnostics: the mismatched assignment is
silently accepted. Depth 100 reports a correct TS2322; depth 101 produces
nothing. The language server is silent too; `textDocument/diagnostic` on a
depth-150 file returns `items: []`, so no squiggle appears in the editor
(verified on `tsc --lsp --stdio` built from main).

## 🙂 Expected behavior

At minimum `TS2321: Excessive stack depth comparing types`, like the JS build
has always emitted on this input and like the native previews emitted until
August; ideally the real `TS2322` at the leaf. Silently accepting mismatched
code is a soundness hole.

## Additional information about the issue

Up-front disclosure: I've been running an AI agent on a side project doing
compiler differential-fuzzing research, and it surfaced this. I've verified
everything below by hand before filing; if AI-assisted reports aren't welcome
here, just close this, no harm done.

Root cause: the bail at `tsc/internal/checker/relater.go:3133` returns a bare
`TernaryMaybe`, and `checkTypeRelatedToEx` ends `return result != TernaryFalse`
(relater.go:397); so "indeterminate" maps to `true` (related). Since
`r.overflow` is never set and nothing reaches `r.errorChain`, the bail produces
no diagnostic. Before #4913 this was `r.overflow = true; return TernaryFalse`,
the JS implementation's behavior, which surfaces TS2321 via
`RelationComparisonResultOverflow`.

To be clear, the intent of #4913 looks right to me; removing spurious TS2321s
on infinitely-recursive-but-fine types was a real fix (typescript-go #4807,
#4465, #1730), and this is now just a backstop behind `isDeeplyNestedType`.
The regression test it added (`veryDeepRelations.ts`) covers two equal-shaped
chains; the uncovered case is a chain pair that differs at the leaf, where the
same "indeterminate" answer now returns a wrong *positive* verdict. The
neighboring fuse (`r.relationCount <= 0`) still does
`r.overflow = true; return TernaryFalse`; this bail is the only quiet one.

Trigger geometry: the fuse counts `sourceStack`/`targetStack` frames; one per
instantiation compared; so the repro needs 101 literal nested instantiations.
(Composed aliases like `W50<W50<...>>` compress the frame count and do NOT
trigger.) Reachable forms therefore include compiler-generated shapes; deep
alias chains from codegen; without visibly pathological syntax.

Suggested fix: restoring `r.overflow = true; return TernaryFalse` recovers 5.x
behavior; if #4913's false-positive fix must be preserved, a softer variant -
mark the entry overflow and surface a diagnostic only when the fuse trips
while elaborating a genuine mismatch; is presumably the right cut. The
`overflow` machinery is intact and already wired for it.

Extended evidence (optional, all reproducible): a 45-case differential map
across 11 type-construct families (28 confirmed silent accepts at depth ≥101),
the LSP session probe, and a realistic typedef-chain repro live in
https://github.com/ChloeVPin/project-chimera (runners under `linux/`, results
under `data/`). Happy to paste anything specific inline if that helps review.
