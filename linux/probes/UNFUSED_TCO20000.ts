import { EvolveTCO, EvolveStrictNonTCO } from "../../src/type_engine/rule110";
type Tape8 = [0, 1, 1, 0, 1, 1, 1, 0];
type _Probe = EvolveTCO<Tape8, 20000>;
export type { _Probe };
