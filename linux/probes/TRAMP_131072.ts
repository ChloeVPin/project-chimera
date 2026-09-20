import { EvolveTCO, EvolveStrictNonTCO } from "../../src/type_engine/rule110";
import { EvolvePow2 } from "../../src/type_engine/log_rule110";
import { Bit } from "../../src/type_engine/cells";
type Tape8 = [0, 1, 1, 0, 1, 1, 1, 0];
type _Probe = EvolvePow2<Tape8, 17>;
export type { _Probe };
