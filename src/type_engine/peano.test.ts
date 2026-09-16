/**
 * Project Chimera: Verification Suite for Peano & Ackermann Engine
 */

import { Equal, staticAssert } from './assertions';
import { Ackermann, Add, Mul, NatToPeano, PeanoToNat } from './peano';

// Addition: 3 + 4 = 7
type Three = NatToPeano<3>;
type Four = NatToPeano<4>;
type Seven = Add<Three, Four>;
staticAssert<Equal<PeanoToNat<Seven>, 7>>();

// Multiplication: 3 * 4 = 12
type Twelve = Mul<Three, Four>;
staticAssert<Equal<PeanoToNat<Twelve>, 12>>();

// Ackermann base cases:
// A(0, 2) = 3
type A02 = Ackermann<NatToPeano<0>, NatToPeano<2>>;
staticAssert<Equal<PeanoToNat<A02>, 3>>();

// A(1, 2) = 4
type A12 = Ackermann<NatToPeano<1>, NatToPeano<2>>;
staticAssert<Equal<PeanoToNat<A12>, 4>>();

// A(2, 1) = 5
type A21 = Ackermann<NatToPeano<2>, NatToPeano<1>>;
staticAssert<Equal<PeanoToNat<A21>, 5>>();

// A(2, 2) = 7
type A22 = Ackermann<NatToPeano<2>, NatToPeano<2>>;
staticAssert<Equal<PeanoToNat<A22>, 7>>();
