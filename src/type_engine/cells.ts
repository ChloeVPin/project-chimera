/**
 * Project Chimera: Cellular Automaton Primitives & Local Transition Semantics
 * 
 * Formal Operational Semantics:
 * Let Σ = {0, 1} be the cell alphabet.
 * A configuration c ∈ Σ^Z (or Σ^N with boundary conditions).
 * An elementary cellular automaton local rule is a mapping:
 *   f: Σ × Σ × Σ -> Σ
 * 
 * For Rule 110 (01101110_2 = 110_10):
 *   f(1, 1, 1) = 0
 *   f(1, 1, 0) = 1
 *   f(1, 0, 1) = 1
 *   f(1, 0, 0) = 0
 *   f(0, 1, 1) = 1
 *   f(0, 1, 0) = 1
 *   f(0, 0, 1) = 1
 *   f(0, 0, 0) = 0
 * 
 * Proven Turing-complete by Matthew Cook (2004) by emulating cyclic tag systems.
 */

export type Bit = 0 | 1;

/**
 * Local transition rule for Rule 110.
 * Directly evaluated by the compiler's conditional type reduction engine.
 */
export type Rule110Transition<L extends Bit, C extends Bit, R extends Bit> =
  [L, C, R] extends [1, 1, 1] ? 0 :
  [L, C, R] extends [1, 1, 0] ? 1 :
  [L, C, R] extends [1, 0, 1] ? 1 :
  [L, C, R] extends [1, 0, 0] ? 0 :
  [L, C, R] extends [0, 1, 1] ? 1 :
  [L, C, R] extends [0, 1, 0] ? 1 :
  [L, C, R] extends [0, 0, 1] ? 1 :
  [L, C, R] extends [0, 0, 0] ? 0 :
  never;

/**
 * Rule 30 local transition (Chaotic, Class III behavior):
 * 00011110_2 = 30_10
 */
export type Rule30Transition<L extends Bit, C extends Bit, R extends Bit> =
  [L, C, R] extends [1, 1, 1] ? 0 :
  [L, C, R] extends [1, 1, 0] ? 0 :
  [L, C, R] extends [1, 0, 1] ? 0 :
  [L, C, R] extends [1, 0, 0] ? 1 :
  [L, C, R] extends [0, 1, 1] ? 1 :
  [L, C, R] extends [0, 1, 0] ? 1 :
  [L, C, R] extends [0, 0, 1] ? 1 :
  [L, C, R] extends [0, 0, 0] ? 0 :
  never;

/**
 * Rule 90 local transition (Additive, Sierpinski fractal):
 * Equivalent to L XOR R.
 */
export type Rule90Transition<L extends Bit, C extends Bit, R extends Bit> =
  [L, R] extends [1, 0] ? 1 :
  [L, R] extends [0, 1] ? 1 :
  0;
