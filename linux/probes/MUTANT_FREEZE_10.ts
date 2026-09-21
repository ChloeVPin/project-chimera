import { EvolveTCO, EvolveStrictNonTCO } from "../../src/type_engine/rule110";
import { EvolvePow2 } from "../../src/type_engine/log_rule110";
import { Bit } from "../../src/type_engine/cells";
type Tape8 = [0, 1, 1, 0, 1, 1, 1, 0];
type QuaternaryFreeze<Depth extends number, Path extends readonly unknown[] = []> =
  Path['length'] extends Depth ? 1 :
  [QuaternaryFreeze<Depth, [0, ...Path]>, QuaternaryFreeze<Depth, [1, ...Path]>,
   QuaternaryFreeze<Depth, [2, ...Path]>, QuaternaryFreeze<Depth, [3, ...Path]>] extends [infer A, infer B, infer C, infer D] ? [A, B, C, D] : never;
type _Probe = QuaternaryFreeze<10>;
export type { _Probe };
