import { EvolveTCO, EvolveStrictNonTCO } from "../../src/type_engine/rule110";
import { EvolvePow2 } from "../../src/type_engine/log_rule110";
import { Bit } from "../../src/type_engine/cells";
type Tape8 = [0, 1, 1, 0, 1, 1, 1, 0];

type QFreezeTag<Depth extends number, Tag extends number, Path extends readonly unknown[] = []> =
  Path['length'] extends Depth ? Tag :
  [QFreezeTag<Depth, Tag, [0, ...Path]>, QFreezeTag<Depth, Tag, [1, ...Path]>,
   QFreezeTag<Depth, Tag, [2, ...Path]>, QFreezeTag<Depth, Tag, [3, ...Path]>] extends [infer A, infer B, infer C, infer D] ? [A, B, C, D] : never;
type Probe0 = QFreezeTag<8, 0>;
type Probe1 = QFreezeTag<8, 1>;
type Probe2 = QFreezeTag<8, 2>;
type Probe3 = QFreezeTag<8, 3>;
type Probe4 = QFreezeTag<8, 4>;
type Probe5 = QFreezeTag<8, 5>;
type Probe6 = QFreezeTag<8, 6>;
type Probe7 = QFreezeTag<8, 7>;
type Probe8 = QFreezeTag<8, 8>;
type Probe9 = QFreezeTag<8, 9>;
export type { Probe0 };
