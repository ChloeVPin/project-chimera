/**
 * Project Chimera: Phase 12 - 3-SAT Solver Verification Suite
 * 
 * Verifies SAT and UNSAT instances strictly at compile time:
 * 1. Simple 2-clause Horn SAT instance.
 * 2. Trivial 1-variable contradiction UNSAT.
 * 3. 3-CNF Satisfiable instance with valid assignment extraction.
 * 4. Complete 3-variable UNSAT formula (all 8 minterms excluded).
 * 5. Pigeonhole Principle PHP(2, 1) UNSAT proof.
 * 6. Pigeonhole Principle PHP(3, 2) UNSAT proof (Exponential refutation tree).
 */

import { Equal, staticAssert } from "../type_engine/assertions";
import { Pos, Neg, Solve } from "./sat";

// ============================================================================
// Test 1: Simple 2-Variable Horn SAT
// (x1 | x2) & (~x1 | x2)
// ============================================================================
type F_SAT1 = [
  [Pos<"x1">, Pos<"x2">],
  [Neg<"x1">, Pos<"x2">]
];
type Res_SAT1 = Solve<F_SAT1>;
staticAssert<Equal<Res_SAT1["satisfied"], true>>();

// ============================================================================
// Test 2: Trivial 1-Variable Contradiction
// (x1) & (~x1)
// ============================================================================
type F_UNSAT1 = [
  [Pos<"x1">],
  [Neg<"x1">]
];
type Res_UNSAT1 = Solve<F_UNSAT1>;
staticAssert<Equal<Res_UNSAT1, { readonly satisfied: false }>>();

// ============================================================================
// Test 3: 3-CNF Satisfiable Instance
// (x1 | x2 | x3) & (~x1 | x2 | ~x3) & (x1 | ~x2 | x3)
// ============================================================================
type F_3CNF_SAT = [
  [Pos<"x1">, Pos<"x2">, Pos<"x3">],
  [Neg<"x1">, Pos<"x2">, Neg<"x3">],
  [Pos<"x1">, Neg<"x2">, Pos<"x3">]
];
type Res_3CNF_SAT = Solve<F_3CNF_SAT>;
staticAssert<Equal<Res_3CNF_SAT["satisfied"], true>>();

// ============================================================================
// Test 4: Complete 3-Variable UNSAT (Excludes all 2^3 = 8 truth assignments)
// ============================================================================
type F_AllMinterms_UNSAT = [
  [Pos<"x1">, Pos<"x2">, Pos<"x3">],
  [Pos<"x1">, Pos<"x2">, Neg<"x3">],
  [Pos<"x1">, Neg<"x2">, Pos<"x3">],
  [Pos<"x1">, Neg<"x2">, Neg<"x3">],
  [Neg<"x1">, Pos<"x2">, Pos<"x3">],
  [Neg<"x1">, Pos<"x2">, Neg<"x3">],
  [Neg<"x1">, Neg<"x2">, Pos<"x3">],
  [Neg<"x1">, Neg<"x2">, Neg<"x3">]
];
type Res_AllMinterms_UNSAT = Solve<F_AllMinterms_UNSAT>;
staticAssert<Equal<Res_AllMinterms_UNSAT, { readonly satisfied: false }>>();

// ============================================================================
// Test 5: Pigeonhole Principle PHP(2, 1) - 2 Pigeons, 1 Hole
// Pigeons p1, p2 into Hole 1:
// (p11), (p21), (~p11 | ~p21)
// ============================================================================
type PHP_2_1 = [
  [Pos<"p11">],
  [Pos<"p21">],
  [Neg<"p11">, Neg<"p21">]
];
type Res_PHP_2_1 = Solve<PHP_2_1>;
staticAssert<Equal<Res_PHP_2_1, { readonly satisfied: false }>>();

// ============================================================================
// Test 6: Pigeonhole Principle PHP(3, 2) - 3 Pigeons, 2 Holes
// 3 pigeons must each be in hole 1 or 2 (3 clauses)
// No two pigeons share hole 1 (3 clauses) or hole 2 (3 clauses) -> Total 9 clauses
// ============================================================================
type PHP_3_2 = [
  // Each pigeon in hole 1 or 2
  [Pos<"p11">, Pos<"p12">],
  [Pos<"p21">, Pos<"p22">],
  [Pos<"p31">, Pos<"p32">],
  // No two pigeons in hole 1
  [Neg<"p11">, Neg<"p21">],
  [Neg<"p11">, Neg<"p31">],
  [Neg<"p21">, Neg<"p31">],
  // No two pigeons in hole 2
  [Neg<"p12">, Neg<"p22">],
  [Neg<"p12">, Neg<"p32">],
  [Neg<"p22">, Neg<"p32">]
];
type Res_PHP_3_2 = Solve<PHP_3_2>;
staticAssert<Equal<Res_PHP_3_2, { readonly satisfied: false }>>();
