/**
 * Project Chimera: Phase 2 - Circuit Breaker Stress Testing & Breadth Vulnerabilities
 * 
 * Formal Hypothesis:
 * The compiler's circuit breaker (TS2589) is primarily a 1D depth-counter:
 *   instantiationDepth <= 48 (non-TCO)
 *   tailCount <= 999 (TCO)
 * 
 * Because the circuit breaker fails to account for branching factor b,
 * a type computation with branching factor b > 1 can generate b^d instantiations
 * while keeping d <= 25 << 48.
 * This should bypass the TS2589 depth fuse and cause super-exponential memory
 * consumption, leading to either silent process termination, extreme wall-clock
 * freezing, or JavaScript V8 Heap Out-Of-Memory (OOM).
 */

// 1. Binary Tree Instantiation (b = 2)
export type BinaryBranch<T> = [T, T];

export type ExpTree<
  Depth extends number,
  Counter extends readonly unknown[] = []
> = Counter['length'] extends Depth
  ? 0
  : BinaryBranch<ExpTree<Depth, [unknown, ...Counter]>>;

// 2. Distributive Cartesian Product Explosion
// Generates 2^N union variants through distributive conditionals
export type UnionBit = 0 | 1;

export type UnionProduct<T extends readonly unknown[], U extends readonly unknown[]> =
  T extends unknown
    ? U extends unknown
      ? [T, U]
      : never
    : never;

export type Pow2Union<
  N extends number,
  Acc = 0 | 1,
  Counter extends readonly unknown[] = [unknown]
> = Counter['length'] extends N
  ? Acc
  : Pow2Union<N, Acc extends unknown ? [Acc, 0] | [Acc, 1] : never, [unknown, ...Counter]>;
