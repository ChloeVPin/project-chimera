/**
 * Project Chimera: Rule 110 Universal Cellular Automaton Engine
 * 
 * Formal Specification:
 * - Tape: T ∈ {0, 1}^N represented as a tuple type `readonly Bit[]`.
 * - Local evolution: f_110(L, C, R).
 * - Boundary conditions:
 *     1. Zero-Padded (Dirichlet quiescent boundary): T[-1] = 0, T[N] = 0.
 *     2. Periodic (Toroidal boundary): T[-1] = T[N-1], T[N] = T[0].
 * - Global Evolution Operator:
 *     Evolve^t(T) = f_110^t(T)
 */

import { Bit, Rule110Transition } from './cells';

// ============================================================================
// Zero-Padded Step (Dirichlet Quiescent Boundary)
// ============================================================================

/**
 * Interior walker for zero-padded tape.
 * Accumulator-passing style (Tail Call Optimized).
 */
type StepZeroPaddedWorker<
  Prev extends Bit,
  Curr extends Bit,
  Rest extends readonly Bit[],
  Acc extends readonly Bit[] = []
> = Rest extends [infer Next extends Bit, ...infer Tail extends Bit[]]
  ? StepZeroPaddedWorker<Curr, Next, Tail, [...Acc, Rule110Transition<Prev, Curr, Next>]>
  : [...Acc, Rule110Transition<Prev, Curr, 0>];

/**
 * Performs a single time-step evolution with quiescent zero boundary.
 */
export type StepZeroPadded<Tape extends readonly Bit[]> =
  Tape extends []
    ? []
    : Tape extends [infer Only extends Bit]
      ? [Rule110Transition<0, Only, 0>]
      : Tape extends [infer First extends Bit, infer Second extends Bit, ...infer Rest extends Bit[]]
        ? StepZeroPaddedWorker<First, Second, Rest, [Rule110Transition<0, First, Second>]>
        : never;

// ============================================================================
// Periodic Step (Toroidal Boundary)
// ============================================================================

type StepPeriodicWorker<
  First extends Bit,
  Prev extends Bit,
  Curr extends Bit,
  Rest extends readonly Bit[],
  Acc extends readonly Bit[] = []
> = Rest extends [infer Next extends Bit, ...infer Tail extends Bit[]]
  ? StepPeriodicWorker<First, Curr, Next, Tail, [...Acc, Rule110Transition<Prev, Curr, Next>]>
  : [...Acc, Rule110Transition<Prev, Curr, First>];

/**
 * Performs a single time-step evolution with periodic (wrap-around) boundary.
 */
export type StepPeriodic<Tape extends readonly Bit[]> =
  Tape extends []
    ? []
    : Tape extends [infer Only extends Bit]
      ? [Rule110Transition<Only, Only, Only>]
      : Tape extends [...infer Init extends Bit[], infer Last extends Bit]
        ? Tape extends [infer First extends Bit, infer Second extends Bit, ...infer Rest extends Bit[]]
          ? StepPeriodicWorker<First, Last, First, [Second, ...Rest], []>
          : never
        : never;

// ============================================================================
// Multi-Step Evolution Engines
// ============================================================================

/**
 * Tail-Call Optimized (TCO) Evolution Engine:
 * Employs accumulator pattern to allow deep compiler recursion.
 */
export type EvolveTCO<
  Tape extends readonly Bit[],
  Steps extends number,
  Counter extends readonly unknown[] = []
> = Counter['length'] extends Steps
  ? Tape
  : StepZeroPadded<Tape> extends infer Next extends readonly Bit[]
    ? EvolveTCO<Next, Steps, [...Counter, unknown]>
    : never;

/**
 * Periodic TCO Evolution Engine
 */
export type EvolvePeriodicTCO<
  Tape extends readonly Bit[],
  Steps extends number,
  Counter extends readonly unknown[] = []
> = Counter['length'] extends Steps
  ? Tape
  : StepPeriodic<Tape> extends infer Next extends readonly Bit[]
    ? EvolvePeriodicTCO<Next, Steps, [...Counter, unknown]>
    : never;

/**
 * Strict Non-TCO Evolution Engine:
 * Employs tuple spread syntax `[unknown, ...Recurse]`, which forces the compiler
 * to maintain a suspended stack frame waiting for inner type reduction.
 * Triggers the compiler's non-TCO stack recursion circuit breaker at depth = 49.
 */
export type EvolveStrictNonTCO<
  Tape extends readonly Bit[],
  Steps extends number,
  Counter extends readonly unknown[] = []
> = Counter['length'] extends Steps
  ? [Tape]
  : [unknown, ...EvolveStrictNonTCO<StepZeroPadded<Tape>, Steps, [...Counter, unknown]>];


/**
 * Full Simulation History Collector:
 * Evaluates the full spacetime grid: matrix of dimensions (Steps + 1) x Width.
 */
export type EvolveHistory<
  Current extends readonly Bit[],
  Steps extends number,
  History extends readonly (readonly Bit[])[] = [Current]
> = History['length'] extends Steps
  ? History
  : StepZeroPadded<Current> extends infer Next extends readonly Bit[]
    ? EvolveHistory<Next, Steps, [...History, Next]>
    : never;
