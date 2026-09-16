/**
 * Project Chimera: Type-Level Verification Suite for Rule 110 Engine
 * 
 * All assertions are computed at COMPILE TIME via type checking.
 * No JavaScript bytecode is generated (`noEmit: true`).
 */

import { Equal, staticAssert } from './assertions';
import { StepZeroPadded, EvolveTCO, EvolveHistory, StepPeriodic } from './rule110';

// Test Vector 1: Standard Quiescent Boundary Step
type InitialTape = [0, 1, 1, 0, 1, 1, 1, 0];
type ExpectedStep1 = [1, 1, 1, 1, 1, 0, 1, 0];
type ExpectedStep2 = [1, 0, 0, 0, 1, 1, 1, 0];

type ActualStep1 = StepZeroPadded<InitialTape>;
type ActualStep2 = StepZeroPadded<ActualStep1>;

// Compile-time proof verification:
staticAssert<Equal<ActualStep1, ExpectedStep1>>();
staticAssert<Equal<ActualStep2, ExpectedStep2>>();

// Test Vector 2: Multi-step EvolveTCO
type Evolved2 = EvolveTCO<InitialTape, 2>;
staticAssert<Equal<Evolved2, ExpectedStep2>>();

// Test Vector 3: 5-step evolution
type Evolved5 = EvolveTCO<InitialTape, 5>;
// Step 3 from [1, 0, 0, 0, 1, 1, 1, 0]:
// c0 (0,1,0)->1, c1 (1,0,0)->0, c2 (0,0,0)->0, c3 (0,0,1)->1, c4 (0,1,1)->1, c5 (1,1,1)->0, c6 (1,1,0)->1, c7 (1,0,0)->0
// -> [1, 0, 0, 1, 1, 0, 1, 0]
// Step 4 from [1, 0, 0, 1, 1, 0, 1, 0]:
// c0 (0,1,0)->1, c1 (1,0,0)->0, c2 (0,0,1)->1, c3 (0,1,1)->1, c4 (1,1,0)->1, c5 (1,0,1)->1, c6 (0,1,0)->1, c7 (1,0,0)->0
// -> [1, 0, 1, 1, 1, 1, 1, 0]
// Step 5 from [1, 0, 1, 1, 1, 1, 1, 0]:
// c0 (0,1,0)->1, c1 (1,0,1)->1, c2 (0,1,1)->1, c3 (1,1,1)->0, c4 (1,1,1)->0, c5 (1,1,1)->0, c6 (1,1,0)->1, c7 (1,0,0)->0
// -> [1, 1, 1, 0, 0, 0, 1, 0]
type ExpectedStep5 = [1, 1, 1, 0, 0, 0, 1, 0];
staticAssert<Equal<Evolved5, ExpectedStep5>>();

// Test Vector 4: History Matrix Shape Verification
type History5 = EvolveHistory<InitialTape, 5>;
staticAssert<Equal<History5['length'], 5>>();
staticAssert<Equal<History5[0], InitialTape>>();
staticAssert<Equal<History5[1], ExpectedStep1>>();
staticAssert<Equal<History5[2], ExpectedStep2>>();
// Index 4 corresponds to Step 4: [1, 0, 1, 1, 1, 1, 1, 0]
staticAssert<Equal<History5[4], [1, 0, 1, 1, 1, 1, 1, 0]>>();

// Test Vector 5: Periodic Wrap-around
// Tape: [1, 0, 0]
// c0: (0, 1, 0) -> 1
// c1: (1, 0, 0) -> 0
// c2: (0, 0, 1) -> 1
type PeriodicTest = StepPeriodic<[1, 0, 0]>;
staticAssert<Equal<PeriodicTest, [1, 0, 1]>>();
