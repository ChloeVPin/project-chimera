/**
 * Project Chimera: Phase 12 - Type-Level NP-Completeness & 3-SAT Solver
 * 
 * Formal Foundations:
 * The Cook-Levin Theorem (1971) proved that the Boolean Satisfiability problem (SAT)
 * is NP-complete. 3-SAT is the canonical restriction where every clause has at most
 * 3 literals.
 * 
 * This module implements a pure type-level DPLL / Backtracking solver:
 * - Literals: Pos<V> and Neg<V>
 * - Clauses: Disjunction of literals (readonly Lit[])
 * - Formulas: Conjunction of clauses in Conjunctive Normal Form (readonly Clause[])
 * - Evaluator: Recursively simplifies clauses under partial assignments,
 *   pruning conflicts and branching on unassigned variables.
 * - Output: Either `{ satisfied: true; assignment: Model }` or `{ satisfied: false }`.
 */

// ============================================================================
// 1. AST: Literals, Clauses, and Formulas
// ============================================================================

export type Pos<Name extends string> = { readonly name: Name; readonly sign: true };
export type Neg<Name extends string> = { readonly name: Name; readonly sign: false };
export type Lit = { readonly name: string; readonly sign: boolean };

export type Clause = readonly Lit[];
export type Formula = readonly Clause[];

export type Model = { readonly [k: string]: boolean };

export type SATResult =
  | { readonly satisfied: true; readonly assignment: Model }
  | { readonly satisfied: false };

// ============================================================================
// 2. Clause & Literal Simplification
// ============================================================================

export type EvalLit<L extends Lit, M> =
  L["name"] extends keyof M
    ? M[L["name"]] extends L["sign"]
      ? "true"
      : "false"
    : "unassigned";

export type SimplifyClause<C extends Clause, M, Acc extends readonly Lit[] = []> =
  C extends readonly [infer Head extends Lit, ...infer Tail extends Lit[]]
    ? EvalLit<Head, M> extends "true"
      ? "SAT_CLAUSE"
      : EvalLit<Head, M> extends "false"
        ? SimplifyClause<Tail, M, Acc>
        : SimplifyClause<Tail, M, [...Acc, Head]>
    : Acc;

export type SimplifyFormula<F extends Formula, M, Acc extends readonly Clause[] = []> =
  F extends readonly [infer Head extends Clause, ...infer Tail extends Clause[]]
    ? SimplifyClause<Head, M> extends infer Res
      ? Res extends "SAT_CLAUSE"
        ? SimplifyFormula<Tail, M, Acc>
        : Res extends readonly []
          ? "CONFLICT"
          : Res extends readonly Lit[]
            ? SimplifyFormula<Tail, M, [...Acc, Res]>
            : never
      : never
    : Acc;

// ============================================================================
// 3. DPLL / Backtracking Decision Engine
// ============================================================================

export type Solve<F extends Formula, M = {}> =
  SimplifyFormula<F, M> extends infer Simp
    ? Simp extends "CONFLICT"
      ? { readonly satisfied: false }
      : Simp extends readonly []
        ? { readonly satisfied: true; readonly assignment: { readonly [K in keyof M]: M[K] } }
        : Simp extends readonly [infer FirstClause extends readonly [infer PickLit extends Lit, ...any[]], ...any[]]
          ? PickLit["name"] extends infer VarName extends string
            ? Solve<Simp, M & { readonly [K in VarName]: true }> extends infer TryTrue
              ? TryTrue extends { readonly satisfied: true }
                ? TryTrue
                : Solve<Simp, M & { readonly [K in VarName]: false }>
              : never
            : never
          : { readonly satisfied: false }
    : never;

// Helper to extract boolean value from model
export type GetModelValue<M extends Model, K extends string> =
  K extends keyof M ? M[K] : never;
