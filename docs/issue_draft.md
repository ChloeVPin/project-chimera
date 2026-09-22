# Draft issue — for filing at github.com/microsoft/TypeScript (bug_report template)

*Each section below maps to a field in their bug report form. The AI disclosure goes first
in "Additional information" — their CONTRIBUTING asks for disclosure of AI-assisted work
and the user wants it upfront either way.*

---

## 🔎 Search Terms

`TS2321`, `Excessive stack depth comparing types`, `deeply nested`, `silent accept`,
`no error reported`, `assignable`, `relater`, `TernaryMaybe`, `typescript-go`, `native preview`

## 🕗 Version & Regression Information

- **Affected:** `typescript@next` (verified on 7.1.0-dev.20260922.1 — the nightly channel
  now ships the native compiler). Reproduces on a from-source build of `main`.
- **NOT affected:** `@typescript/native-preview` 7.0.0-dev.20260707.2 and all earlier
  previews (they emit TS2321 correctly). Previews stopped publishing 2026-07-07.
- **NOT affected:** `typescript@5.9.3` — emits TS2321 loudly, as it always has.
- **Changed in commit:** `microsoft/typescript-go` PR
  [#4913](https://github.com/microsoft/typescript-go/pull/4913)
  ("Improve recursion identities and `isDeeplyNestedType`", 12548e2a1, 2026-08-18) —
  the depth-100 bail in `recursiveTypeRelatedTo` changed from
  `r.overflow = true; return TernaryFalse` to `return TernaryMaybe`.

## ⏯ Playground Link

(none — the Playground runs the JS checker, which is unaffected. Repro is 6 lines,
see below.)

## 💻 Code

```ts
type W<T> = { v: T };
type A = W<W<W<...101 levels total...<W<string>>>>>;   // see generator note below
type B = W<W<W<...101 levels total...<W<number>>>>>;
declare const a: A;
const b: B = a;
```

Full literal file (generator, one line):
`'W<'*101 + 'string' + '>'*101` (and same for `number`) —
equivalently `python3 -c "print('W<'*101 + 'string' + '>'*101)"`.

## 🙁 Actual behavior

`tsc --noEmit` exits 0 with **zero diagnostics** — the wrong assignment is silently
accepted. Depth 100 reports correctly; depth 101 goes silent (the fuse trips at a
relation stack of 100). The same silence happens via the language server:
`textDocument/diagnostic` on a depth-150 file returns `items: []` — no squiggle.

## 🙂 Expected behavior

`tsc` should at minimum emit `TS2321: Excessive stack depth comparing types` like the
JS build always has — or better, report the real `TS2322` mismatch at the leaf.
Silently accepting mismatched code is a soundness hole.

## Additional information about the issue

*(first line, verbatim)*

> Up-front disclosure: I've been running an AI agent on a side project doing
> compiler differential-fuzzing research, and it surfaced this. I've verified
> everything below by hand before filing — but if AI-assisted reports aren't
> welcome here, just close this, no harm done.

**Root cause.** The depth fuse at `tsc/internal/checker/relater.go:3133` returns a
bare `TernaryMaybe`. `checkTypeRelatedToEx` ends `return result != TernaryFalse`
(relater.go:397), so `Maybe` maps to `true` — *related* — and since `r.overflow`
is never set and nothing reaches `r.errorChain`, the bail produces no diagnostic at
all. Before #4913 it was `r.overflow = true; return TernaryFalse` (the JS
implementation's behavior, which reports TS2321 via `RelationComparisonResultOverflow`).

I want to be clear the *intent* of #4913 looks correct to me — it eliminated
false-positive TS2321s on infinitely-recursive-but-fine types (typescript-go #4807,
#4465, #1730), and this is just a backstop now that `isDeeplyNestedType` does the
real guarding. The side effect is that the backstop also swallows *genuine*
mismatches, and `Maybe`→`true` means it does so by declaring wrong code *related*.
Notably `r.relationCount <= 0` one branch away still does
`r.overflow = true; return TernaryFalse` — this bail is the only quiet one.

**Trigger geometry** (why it took 100 levels): the fuse counts `sourceStack`/
`targetStack` frames — one per instantiation compared — so it needs 101 literal
nested instantiations to trip. That also means reachable forms include
compiler-generated shapes (deep alias chains from codegen) without any visibly
pathological syntax.

**Suggested fix.** Restoring `r.overflow = true; return TernaryFalse` recovers the
5.x behavior; if #4913's false-positive fix must be preserved, a softer variant —
mark the entry overflow and surface a diagnostic only when the fuse trips while
elaborating a real mismatch — is presumably the right cut. I'll leave that to you
all, but the `overflow` machinery is intact and already wired for it.

**Extended evidence** (optional, all reproducible): a 45-case differential map
across 11 type-construct families — 28 confirmed silent accepts at depth ≥101 —
plus the LSP session probe and a real-world-looking typedef-chain repro are in
https://github.com/ChloeVPin/project-chimera (runners under `linux/`, results under
`data/`). Happy to paste anything specific inline if that's easier to review.
