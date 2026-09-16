/**
 * Project Chimera: Verification Suite for Logarithmic Bypass Engine
 * 
 * Verifies:
 * 1. Semantic equivalence: Trampoline512<T, 1> === EvolveTCO<T, 512>
 * 2. Crossing the 1,000-step ceiling: S = 1,024 passes cleanly
 * 3. Deep horizon: S = 65,536 passes cleanly
 */

import { Equal, staticAssert } from './assertions';
import { EvolveTCO } from './rule110';
import { EvolvePow2, StepChunk512, Trampoline512 } from './log_rule110';

type InitialTape = [0, 1, 1, 0, 1, 1, 1, 0];

// Test 1: Equivalence between direct TCO and single-chunk trampoline
type Direct512 = EvolveTCO<InitialTape, 512>;
type TrampolineSingle = StepChunk512<InitialTape>;
staticAssert<Equal<Direct512, TrampolineSingle>>();

type Trampoline1Chunk = Trampoline512<InitialTape, 1>;
staticAssert<Equal<Direct512, Trampoline1Chunk>>();

// Test 2: Crossing the 999-step fuel limit (S = 1,024 = 2^10)
type Evolved1024 = EvolvePow2<InitialTape, 10>;
// Verify it yields a concrete 8-bit tape:
staticAssert<Equal<Evolved1024['length'], 8>>();

// Test 3: S = 4,096 = 2^12
type Evolved4096 = EvolvePow2<InitialTape, 12>;
staticAssert<Equal<Evolved4096['length'], 8>>();

// Test 4: Extreme Horizon S = 65,536 = 2^16
type Evolved65536 = EvolvePow2<InitialTape, 16>;
staticAssert<Equal<Evolved65536['length'], 8>>();
