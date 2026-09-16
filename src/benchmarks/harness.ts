/**
 * Project Chimera: Automated Compiler Telemetry & Benchmark Harness
 * 
 * Formal Methodology:
 * Measures compiler thermodynamic costs (Wall time, Check time, Heap memory,
 * OS RSS, Type count, and Instantiation counts) across parametric variations
 * of type-level computational complexity.
 * 
 * Each benchmark runs in an isolated process to eliminate type-memoization
 * cache leakage across runs.
 */

import * as fs from 'fs';
import * as path from 'path';
import { execSync } from 'child_process';

export interface BenchmarkMetrics {
  name: string;
  parameters: Record<string, unknown>;
  success: boolean;
  exitCode: number;
  tsErrors: string[];
  checkTimeSec: number;
  totalTimeSec: number;
  parseTimeSec: number;
  bindTimeSec: number;
  compilerMemoryUsedKB: number;
  compilerMemoryAllocs: number;
  typeCount: number;
  instantiationCount: number;
  symbolCount: number;
  identifierCount: number;
  wallClockMs: number;
}

export class CompilerHarness {
  private tempDir: string;

  constructor(tempDirName: string = '.chimera_bench') {
    this.tempDir = path.resolve(process.cwd(), tempDirName);
    if (!fs.existsSync(this.tempDir)) {
      fs.mkdirSync(this.tempDir, { recursive: true });
    }
  }

  /**
   * Run a specific benchmark test case by generating isolated TypeScript source
   * and running tsc with extended diagnostics.
   */
  public runCase(
    name: string,
    sourceCode: string,
    parameters: Record<string, unknown>
  ): BenchmarkMetrics {
    const filename = path.join(this.tempDir, `${name}_${Date.now()}_${Math.floor(Math.random() * 1000)}.ts`);
    fs.writeFileSync(filename, sourceCode);

    const startTime = Date.now();
    let stdout = '';
    let stderr = '';
    let exitCode = 0;

    try {
      stdout = execSync(`npx tsc --noEmit --extendedDiagnostics --ignoreConfig --strict "${filename}"`, {
        cwd: process.cwd(),
        stdio: ['pipe', 'pipe', 'pipe'],
        maxBuffer: 10 * 1024 * 1024
      }).toString();
    } catch (err: any) {
      exitCode = err.status ?? 1;
      stdout = err.stdout?.toString() ?? '';
      stderr = err.stderr?.toString() ?? '';
    } finally {
      // Clean up temporary file
      if (fs.existsSync(filename)) {
        fs.unlinkSync(filename);
      }
    }

    const wallClockMs = Date.now() - startTime;
    const combinedOutput = stdout + '\n' + stderr;

    // Parse TS error codes (e.g. TS2589)
    const errorMatches = Array.from(combinedOutput.matchAll(/error (TS\d+):/g)).map(m => m[1]);
    const tsErrors = Array.from(new Set(errorMatches));

    // Parse extended diagnostics
    const parseField = (regex: RegExp): number => {
      const match = combinedOutput.match(regex);
      return match ? parseFloat(match[1]) : 0;
    };

    const types = parseField(/Types:\s+(\d+)/);
    const instantiations = parseField(/Instantiations:\s+(\d+)/);
    const symbols = parseField(/Symbols:\s+(\d+)/);
    const identifiers = parseField(/Identifiers:\s+(\d+)/);
    const memoryUsedKB = parseField(/Memory used:\s+(\d+)K/);
    const memoryAllocs = parseField(/Memory allocs:\s+(\d+)/);
    const parseTimeSec = parseField(/Parse time:\s+([\d\.]+)s/);
    const bindTimeSec = parseField(/Bind time:\s+([\d\.]+)s/);
    const checkTimeSec = parseField(/Check time:\s+([\d\.]+)s/);
    const totalTimeSec = parseField(/Total time:\s+([\d\.]+)s/);

    return {
      name,
      parameters,
      success: exitCode === 0,
      exitCode,
      tsErrors,
      checkTimeSec,
      totalTimeSec,
      parseTimeSec,
      bindTimeSec,
      compilerMemoryUsedKB: memoryUsedKB,
      compilerMemoryAllocs: memoryAllocs,
      typeCount: types,
      instantiationCount: instantiations,
      symbolCount: symbols,
      identifierCount: identifiers,
      wallClockMs
    };
  }

  public cleanup(): void {
    if (fs.existsSync(this.tempDir)) {
      fs.rmSync(this.tempDir, { recursive: true, force: true });
    }
  }
}
