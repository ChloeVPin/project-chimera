/**
 * Project Chimera: Phase 5 - Logarithmic Bypass Benchmark Suite
 * 
 * Empirically tests the trampolined evolution engine across horizons
 * exceeding the compiler's 999-step ceiling:
 *   S ∈ [1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072]
 */

import * as fs from 'fs';
import * as path from 'path';
import { CompilerHarness, BenchmarkMetrics } from './harness';

async function runPhase5() {
  const harness = new CompilerHarness('.chimera_bench_p5');
  const results: {
    logarithmic_horizons: BenchmarkMetrics[];
  } = {
    logarithmic_horizons: []
  };

  console.log('================================================================');
  console.log('Project Chimera: Phase 5 Logarithmic Bypass Benchmark Suite');
  console.log('Breaking the 999-Step Ceiling via Trampolined Chunking');
  console.log('================================================================\n');

  const logRule110Path = path.resolve(process.cwd(), 'src/type_engine/log_rule110');
  const horizons = [
    { exponent: 10, chunks: 2, steps: 1024 },
    { exponent: 11, chunks: 4, steps: 2048 },
    { exponent: 12, chunks: 8, steps: 4096 },
    { exponent: 13, chunks: 16, steps: 8192 },
    { exponent: 14, chunks: 32, steps: 16384 },
    { exponent: 15, chunks: 64, steps: 32768 },
    { exponent: 16, chunks: 128, steps: 65536 },
    { exponent: 17, chunks: 256, steps: 131072 }
  ];

  for (const h of horizons) {
    const code = `
import { Trampoline512 } from '${logRule110Path}';
type InitialTape = [0, 1, 1, 0, 1, 1, 1, 0];
type Result = Trampoline512<InitialTape, ${h.chunks}>;
`;
    const res = harness.runCase(`exp5_s${h.steps}`, code, {
      steps: h.steps,
      chunks: h.chunks,
      exponent: h.exponent
    });
    results.logarithmic_horizons.push(res);
    console.log(`  S = ${h.steps.toString().padStart(6)} (2^${h.exponent.toString().padStart(2)}, ${h.chunks.toString().padStart(3)} chunks) | Inst: ${res.instantiationCount.toString().padStart(7)} | Mem: ${(res.compilerMemoryUsedKB / 1024).toFixed(1).padStart(6)} MB | CheckTime: ${res.checkTimeSec.toFixed(3)}s | Status: ${res.success ? 'PASS' : `FAIL (${res.tsErrors.join(',')})`}`);
  }

  // Save results
  const dataDir = path.resolve(process.cwd(), 'data');
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }
  const outputPath = path.join(dataDir, 'phase5_logarithmic_results.json');
  fs.writeFileSync(outputPath, JSON.stringify(results, null, 2));
  console.log(`\n[+] Phase 5 Logarithmic Bypass Results saved to: ${outputPath}`);

  harness.cleanup();
}

runPhase5().catch(console.error);
