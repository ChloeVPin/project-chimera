/**
 * Project Chimera: Act V / Phase L1 - Linux x86_64 Fuse Hierarchy Probe
 *
 * Replicates the Phase 1 tri-fuse mapping on Linux (tsc 7.0.2 native compiler):
 *   Fuse 1: Non-TCO instantiation depth fuse (~48 on Darwin)
 *   Fuse 2: TCO tail-call fuel fuse (999 on Darwin)
 *   Fuse 3: Global type-instantiation heap ceiling (~5.03M on Darwin)
 *
 * Probe variants are toggled via the PROBE variant type below — each file
 * instantiation is compiled in isolation by linux/run_fuse_probes.py.
 */

import { EvolveTCO, EvolveStrictNonTCO } from "../../src/type_engine/rule110";
import { EvolvePow2, Trampoline512 } from "../../src/type_engine/log_rule110";
import { QuaternaryFreeze } from "../../src/stress_tests/pathological_freeze";

export type Tape8 = [0, 1, 1, 0, 1, 1, 1, 0];

// --- Fuse 2 probes: TCO fuel counter ---
export type TCO_999 = EvolveTCO<Tape8, 999>;
export type TCO_1000 = EvolveTCO<Tape8, 1000>;
export type TCO_2000 = EvolveTCO<Tape8, 2000>;

// --- Fuse 1 probes: non-TCO depth fuse ---
export type NONTCO_40 = EvolveStrictNonTCO<Tape8, 40>;
export type NONTCO_48 = EvolveStrictNonTCO<Tape8, 48>;
export type NONTCO_49 = EvolveStrictNonTCO<Tape8, 49>;
export type NONTCO_60 = EvolveStrictNonTCO<Tape8, 60>;

// --- Trampoline bypass probes ---
export type TRAMP_1024 = EvolvePow2<Tape8, 10>;
export type TRAMP_65536 = EvolvePow2<Tape8, 16>;
export type TRAMP_131072 = EvolvePow2<Tape8, 17>;

// --- Fuse 3 probes: heap ceiling (exponential breadth) ---
export type FREEZE_7 = QuaternaryFreeze<7>;   // 4^7 = 16,384 leaves
export type FREEZE_8 = QuaternaryFreeze<8>;   // 4^8 = 65,536 leaves
export type FREEZE_9 = QuaternaryFreeze<9>;   // 4^9 = 262,144 leaves
export type FREEZE_10 = QuaternaryFreeze<10>; // 4^10 = 1,048,576 leaves
export type FREEZE_11 = QuaternaryFreeze<11>; // 4^11 = 4,194,304 leaves
export type FREEZE_12 = QuaternaryFreeze<12>; // 4^12 = 16,777,216 leaves
