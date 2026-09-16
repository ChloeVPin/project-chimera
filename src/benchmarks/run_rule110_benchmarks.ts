/**
 * Project Chimera: Phase 1 Empirical Experiment Runner
 * 
 * Executes systematic parametric sweeps across:
 * - Temporal depth (S: 1 -> 1000)
 * - Spatial width (W: 5 -> 100)
 * - TCO vs Non-TCO circuit breaker limits
 * - History matrix instantiation overhead
 */

import * as fs from 'fs';
import * as path from 'path';
import { CompilerHarness, BenchmarkMetrics } from './harness';

function generateRandomTape(width: number): (0 | 1)[] {
  // Deterministic pseudo-random tape using LCG for absolute reproducibility
  const tape: (0 | 1)[] = [];
  let seed = 42;
  for (let i = 0; i < width; i++) {
    seed = (seed * 1664525 + 1013904223) % 4294967296;
    tape.push(((seed >>> 16) & 1) as 0 | 1);
  }
  // Ensure at least one 1 to avoid trivial null dynamics
  if (!tape.includes(1)) {
    (tape as (0 | 1)[])[Math.floor(width / 2)] = 1;
  }
  return tape;
}

async function run() {
  const harness = new CompilerHarness();
  const results: {
    exp1A_temporal: BenchmarkMetrics[];
    exp1B_spatial: BenchmarkMetrics[];
    exp1C_fuseComparison: BenchmarkMetrics[];
    exp1D_history: BenchmarkMetrics[];
  } = {
    exp1A_temporal: [],
    exp1B_spatial: [],
    exp1C_fuseComparison: [],
    exp1D_history: []
  };

const rule110Path = path.resolve(process.cwd(), 'src/type_engine/rule110');

  // -------------------------------------------------------------------------
  // Experiment 1A: Temporal Scaling (Fixed Width W = 10, Variable S)
  // -------------------------------------------------------------------------
  console.log('>>> Running Experiment 1A: Temporal Scaling (W = 10, S = 1 -> 1000)...');
  const tape10 = generateRandomTape(10);
  const temporalSteps = [1, 5, 10, 25, 50, 100, 200, 400, 600, 800, 950, 990, 999, 1000];

  for (const s of temporalSteps) {
    const code = `
import { EvolveTCO } from '${rule110Path}';
type Tape = [${tape10.join(', ')}];
type Result = EvolveTCO<Tape, ${s}>;
`;
    const res = harness.runCase(`exp1a_w10_s${s}`, code, { width: 10, steps: s, mode: 'TCO' });
    results.exp1A_temporal.push(res);
    console.log(`  S = ${s.toString().padStart(4)} | Instantiations: ${res.instantiationCount.toString().padStart(7)} | CheckTime: ${res.checkTimeSec.toFixed(3)}s | Mem: ${res.compilerMemoryUsedKB}K | Status: ${res.success ? 'PASS' : `FAIL (${res.tsErrors.join(',')})`}`);
  }

  // -------------------------------------------------------------------------
  // Experiment 1B: Spatial Scaling (Fixed S = 10, Variable Width W)
  // -------------------------------------------------------------------------
  console.log('\n>>> Running Experiment 1B: Spatial Scaling (S = 10, W = 5 -> 100)...');
  const widths = [5, 10, 20, 30, 40, 50, 75, 100];

  for (const w of widths) {
    const tape = generateRandomTape(w);
    const code = `
import { EvolveTCO } from '${rule110Path}';
type Tape = [${tape.join(', ')}];
type Result = EvolveTCO<Tape, 10>;
`;
    const res = harness.runCase(`exp1b_w${w}_s10`, code, { width: w, steps: 10, mode: 'TCO' });
    results.exp1B_spatial.push(res);
    console.log(`  W = ${w.toString().padStart(3)} | Instantiations: ${res.instantiationCount.toString().padStart(7)} | CheckTime: ${res.checkTimeSec.toFixed(3)}s | Mem: ${res.compilerMemoryUsedKB}K | Status: ${res.success ? 'PASS' : `FAIL (${res.tsErrors.join(',')})`}`);
  }

  // -------------------------------------------------------------------------
  // Experiment 1C: Fuse Comparison (TCO vs Non-TCO around recursion boundary)
  // -------------------------------------------------------------------------
  console.log('\n>>> Running Experiment 1C: Circuit Breaker Fuse Comparison (TCO vs Non-TCO)...');
  const comparisonSteps = [10, 20, 30, 40, 45, 48, 49, 50, 60];

  for (const s of comparisonSteps) {
    const tape = generateRandomTape(10);
    // Non-TCO (probes the 48-step stack depth limit):
    const nonTcoCode = `
import { EvolveStrictNonTCO } from '${rule110Path}';
type Tape = [${tape.join(', ')}];
type Result = EvolveStrictNonTCO<Tape, ${s}>;
`;
    const resNonTCO = harness.runCase(`exp1c_nontco_s${s}`, nonTcoCode, { width: 10, steps: s, mode: 'StrictNon-TCO' });
    results.exp1C_fuseComparison.push(resNonTCO);

    // TCO:
    const tcoCode = `
import { EvolveTCO } from '${rule110Path}';
type Tape = [${tape.join(', ')}];
type Result = EvolveTCO<Tape, ${s}>;
`;
    const resTCO = harness.runCase(`exp1c_tco_s${s}`, tcoCode, { width: 10, steps: s, mode: 'TCO' });
    results.exp1C_fuseComparison.push(resTCO);

    console.log(`  S = ${s.toString().padStart(2)} | Non-TCO: ${resNonTCO.success ? 'PASS' : `FAIL (${resNonTCO.tsErrors.join(',')})`} (${resNonTCO.instantiationCount} inst) | TCO: ${resTCO.success ? 'PASS' : `FAIL (${resTCO.tsErrors.join(',')})`} (${resTCO.instantiationCount} inst)`);
  }

  // -------------------------------------------------------------------------
  // Experiment 1D: Spacetime History Matrix (W = 10, Variable S)
  // -------------------------------------------------------------------------
  console.log('\n>>> Running Experiment 1D: Spacetime History Matrix Overhead...');
  const historySteps = [1, 5, 10, 25, 50, 100, 200];

  for (const s of historySteps) {
    const tape = generateRandomTape(10);
    const code = `
import { EvolveHistory } from '${rule110Path}';
type Tape = [${tape.join(', ')}];
type Result = EvolveHistory<Tape, ${s}>;
`;
    const res = harness.runCase(`exp1d_history_s${s}`, code, { width: 10, steps: s, mode: 'History' });
    results.exp1D_history.push(res);
    console.log(`  S = ${s.toString().padStart(3)} | Instantiations: ${res.instantiationCount.toString().padStart(7)} | Types: ${res.typeCount.toString().padStart(6)} | CheckTime: ${res.checkTimeSec.toFixed(3)}s | Status: ${res.success ? 'PASS' : `FAIL (${res.tsErrors.join(',')})`}`);
  }

  // Save results
  const dataDir = path.resolve(process.cwd(), 'data');
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }
  const outputPath = path.join(dataDir, 'phase1_rule110_results.json');
  fs.writeFileSync(outputPath, JSON.stringify(results, null, 2));
  console.log(`\n[+] Phase 1 Benchmark Results successfully saved to: ${outputPath}`);

  harness.cleanup();
}

run().catch(console.error);
