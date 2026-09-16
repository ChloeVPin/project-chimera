/**
 * Project Chimera: Phase 2 - Circuit-Breaker Stress Testing & Combinatorial Vulnerabilities
 * 
 * Systematic evaluation of:
 * 1. Binary Tree Instantiation Explosion (Breadth b=2 vs Depth d)
 * 2. Distributive Cartesian Product Explosion (N x N union members)
 * 3. Static vs Dynamic Cycle Detection (TS2456 vs TS2589)
 */

import * as fs from 'fs';
import * as path from 'path';
import { CompilerHarness, BenchmarkMetrics } from './harness';

async function runPhase2() {
  const harness = new CompilerHarness('.chimera_bench_p2');
  const results: {
    exp2A_binaryTree: BenchmarkMetrics[];
    exp2B_cartesianUnion: BenchmarkMetrics[];
    exp2C_cycleDetection: BenchmarkMetrics[];
  } = {
    exp2A_binaryTree: [],
    exp2B_cartesianUnion: [],
    exp2C_cycleDetection: []
  };

  console.log('================================================================');
  console.log('Project Chimera: Phase 2 Circuit-Breaker Stress Testing Suite');
  console.log('================================================================\n');

  // -------------------------------------------------------------------------
  // Experiment 2A: Binary Tree Expansion (Breadth b=2, Depth D = 1 -> 17)
  // -------------------------------------------------------------------------
  console.log('>>> Running Experiment 2A: Binary Tree Expansion (D = 1 -> 17)...');
  const treeDepths = [1, 2, 4, 6, 8, 10, 12, 14, 15, 16, 17];

  for (const d of treeDepths) {
    const code = `
type BranchSum<Depth extends number, Path extends readonly unknown[] = []> =
  Path["length"] extends Depth
    ? 1
    : [BranchSum<Depth, [0, ...Path]>, BranchSum<Depth, [1, ...Path]>] extends [infer A, infer B]
      ? [A, B]
      : never;
type Result = BranchSum<${d}>;
`;
    const res = harness.runCase(`exp2a_tree_d${d}`, code, { depth: d, leaves: Math.pow(2, d) });
    results.exp2A_binaryTree.push(res);
    console.log(`  Depth ${d.toString().padStart(2)} (2^${d} = ${Math.pow(2, d).toString().padStart(6)} leaves) | Inst: ${res.instantiationCount.toString().padStart(7)} | Mem: ${(res.compilerMemoryUsedKB / 1024).toFixed(1).padStart(6)} MB | CheckTime: ${res.checkTimeSec.toFixed(3)}s | Status: ${res.success ? 'PASS' : `FAIL (${res.tsErrors.join(',')})`}`);
  }

  // -------------------------------------------------------------------------
  // Experiment 2B: Distributive Cartesian Product Explosion
  // -------------------------------------------------------------------------
  console.log('\n>>> Running Experiment 2B: Distributive Cartesian Product Explosion...');
  const unionSizes = [50, 100, 200, 400, 600, 800, 1000, 1200];

  for (const size of unionSizes) {
    const membersA = Array.from({ length: size }, (_, i) => `"a${i}"`).join(' | ');
    const membersB = Array.from({ length: size }, (_, i) => `"b${i}"`).join(' | ');
    const code = `
type A = ${membersA};
type B = ${membersB};
type Product<X, Y> = X extends any ? Y extends any ? [X, Y] : never : never;
type Res = Product<A, B>;
`;
    const res = harness.runCase(`exp2b_cartesian_${size}`, code, { size, totalPairs: size * size });
    results.exp2B_cartesianUnion.push(res);
    console.log(`  Size ${size.toString().padStart(4)}x${size.toString().padStart(4)} = ${(size * size).toString().padStart(8)} pairs | Inst: ${res.instantiationCount.toString().padStart(7)} | Mem: ${(res.compilerMemoryUsedKB / 1024).toFixed(1).padStart(6)} MB | CheckTime: ${res.checkTimeSec.toFixed(3)}s | Status: ${res.success ? 'PASS' : `FAIL (${res.tsErrors.join(',')})`}`);
  }

  // -------------------------------------------------------------------------
  // Experiment 2C: Static vs Dynamic Cycle Detection
  // -------------------------------------------------------------------------
  console.log('\n>>> Running Experiment 2C: Static Bind-Time vs Dynamic Check-Time Cycle Detection...');
  
  // Case 1: Direct Unconditional Cycle (Bind-time TS2456)
  const codeDirectCycle = `
type DirectLoop<T> = DirectLoop<[T]>;
type Test = DirectLoop<number>;
`;
  const resDirect = harness.runCase('exp2c_direct_cycle', codeDirectCycle, { mode: 'direct_unconditional' });
  results.exp2C_cycleDetection.push(resDirect);
  console.log(`  Direct Cycle     | Errors: ${resDirect.tsErrors.join(', ')} | Status: ${resDirect.success ? 'PASS' : 'FAIL'}`);

  // Case 2: Conditional Deferred Cycle (Check-time TS2589)
  const codeConditionalCycle = `
type DeferredLoop<T> = T extends unknown ? DeferredLoop<[T]> : never;
type Test = DeferredLoop<number>;
`;
  const resDeferred = harness.runCase('exp2c_deferred_cycle', codeConditionalCycle, { mode: 'deferred_conditional' });
  results.exp2C_cycleDetection.push(resDeferred);
  console.log(`  Deferred Cycle   | Errors: ${resDeferred.tsErrors.join(', ')} | Status: ${resDeferred.success ? 'PASS' : 'FAIL'}`);

  // Save results
  const dataDir = path.resolve(process.cwd(), 'data');
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }
  const outputPath = path.join(dataDir, 'phase2_stress_results.json');
  fs.writeFileSync(outputPath, JSON.stringify(results, null, 2));
  console.log(`\n[+] Phase 2 Benchmark Results successfully saved to: ${outputPath}`);

  harness.cleanup();
}

runPhase2().catch(console.error);
