/**
 * Project Chimera: Phase 5 - The Logarithmic Bypass Engine
 * 
 * Formal Theoretical Hypothesis:
 * The TypeScript compiler enforces a tail-recursion fuel counter fuse of F = 999 steps.
 * In Phase 1, linear evolution halted at S = 1000 with error TS2589.
 * 
 * However, the compiler's fuel counter is dynamically scoped to the contiguous
 * tail-call evaluation chain of a single type alias invocation.
 * By constructing a trampolined chunking operator:
 * 
 *   T_0 --(Evolve_512)--> T_1 --(Evolve_512)--> T_2 ... --(Evolve_512)--> T_k
 * 
 * where each 512-step transition is resolved to a concrete tuple before the outer
 * trampoline initiates the subsequent iteration, the fuel counter resets at each bounce.
 * This permits achieving evolutionary horizons of S = 2^16 = 65,536 and beyond
 * without tripping the TS2589 circuit breaker.
 */

import { Bit } from './cells';
import { EvolveTCO, StepZeroPadded } from './rule110';

// Fixed chunk sizes safely below the 999 fuel threshold
export type ChunkSize128 = 128;
export type ChunkSize256 = 256;
export type ChunkSize512 = 512;

/**
 * Atomic 512-step evolution chunk (evaluated entirely within a single TCO cycle).
 */
export type StepChunk512<Tape extends readonly Bit[]> = EvolveTCO<Tape, ChunkSize512>;

/**
 * Atomic 256-step evolution chunk.
 */
export type StepChunk256<Tape extends readonly Bit[]> = EvolveTCO<Tape, ChunkSize256>;

/**
 * Trampoline Engine (Chunk-level unrolling):
 * Evaluates Chunks * 512 steps.
 * Total Effective Steps:
 *   Chunks = 2   => S = 1,024
 *   Chunks = 8   => S = 4,096
 *   Chunks = 32  => S = 16,384
 *   Chunks = 128 => S = 65,536
 *   Chunks = 256 => S = 131,072
 */
export type Trampoline512<
  Tape extends readonly Bit[],
  Chunks extends number,
  Counter extends readonly unknown[] = []
> = Counter['length'] extends Chunks
  ? Tape
  : StepChunk512<Tape> extends infer NextTape extends readonly Bit[]
    ? Trampoline512<NextTape, Chunks, [...Counter, unknown]>
    : never;

/**
 * Dyadic Power-of-Two Evolution:
 * Maps an exponent K to an evolutionary horizon S = 2^K steps.
 */
export type EvolvePow2<
  Tape extends readonly Bit[],
  Exponent extends 10 | 12 | 14 | 16 | 17
> = Exponent extends 10
  ? Trampoline512<Tape, 2>    // 2 * 512 = 1,024 = 2^10
  : Exponent extends 12
  ? Trampoline512<Tape, 8>    // 8 * 512 = 4,096 = 2^12
  : Exponent extends 14
  ? Trampoline512<Tape, 32>   // 32 * 512 = 16,384 = 2^14
  : Exponent extends 16
  ? Trampoline512<Tape, 128>  // 128 * 512 = 65,536 = 2^16
  : Exponent extends 17
  ? Trampoline512<Tape, 256>  // 256 * 512 = 131,072 = 2^17
  : never;

/**
 * Super-Trampoline (Two-Level Hierarchy):
 * Can evaluate up to 128 * 65,536 = 8,388,608 steps.
 */
export type SuperTrampoline<
  Tape extends readonly Bit[],
  SuperChunks extends number,
  Counter extends readonly unknown[] = []
> = Counter['length'] extends SuperChunks
  ? Tape
  : Trampoline512<Tape, 128> extends infer NextMega extends readonly Bit[]
    ? SuperTrampoline<NextMega, SuperChunks, [...Counter, unknown]>
    : never;
