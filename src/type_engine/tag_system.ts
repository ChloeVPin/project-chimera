/**
 * Project Chimera: Post 2-Tag System Type-Level Computational Engine
 * 
 * Formal Specification (Cocke-Minsky 1961):
 * A Post 2-tag system is a 4-tuple T = (Σ, m, R, w_0) where:
 * - Σ is a finite alphabet of symbols.
 * - m = 2 is the deletion number.
 * - R: Σ -> Σ* is the production function.
 * - w_0 ∈ Σ* is the initial word.
 * 
 * Operational Semantics:
 * Given word w = σ_1 σ_2 ... σ_k:
 * 1. If |w| < 2, the system halts.
 * 2. If |w| >= 2, the next word is w' = σ_3 ... σ_k R(σ_1).
 * 
 * Cocke & Minsky (1961) proved that 2-tag systems are universal (Turing-equivalent).
 */

export interface TagAlphabet {
  [key: string]: readonly string[];
}

/**
 * Single evaluation step of a 2-tag system.
 */
export type Step2Tag<
  Word extends readonly string[],
  Rules extends TagAlphabet
> = Word extends [infer S1 extends string, infer S2 extends string, ...infer Rest extends string[]]
  ? S1 extends keyof Rules
    ? [...Rest, ...Rules[S1]]
    : never
  : []; // Halting condition (|w| < 2)

/**
 * Iterative execution of a 2-tag system with step counter (TCO).
 */
export type Run2Tag<
  Word extends readonly string[],
  Rules extends TagAlphabet,
  Steps extends number,
  Counter extends readonly unknown[] = []
> = Counter['length'] extends Steps
  ? Word
  : Word extends [string, string, ...string[]]
    ? Step2Tag<Word, Rules> extends infer NextWord extends readonly string[]
      ? Run2Tag<NextWord, Rules, Steps, [...Counter, unknown]>
      : never
    : Word; // Terminated early (halted)

/**
 * Canonical Collatz-like 2-tag system (Minsky / Margenstern):
 * A known 2-tag system illustrating non-trivial dynamics.
 * Alphabet: { 'a', 'b', 'c' }
 * R(a) = ['b', 'c']
 * R(b) = ['a']
 * R(c) = ['a', 'a', 'a']
 */
export type CollatzTagRules = {
  a: ['b', 'c'];
  b: ['a'];
  c: ['a', 'a', 'a'];
};
