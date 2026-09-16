/**
 * Project Chimera: Type-Level Self-Reference & Quine Engine
 * 
 * Formal Foundation:
 * Kleene's Second Recursion Theorem (1938) & Rogers' Fixed-Point Theorem:
 * For every computable operator F, there exists an index e such that:
 *     φ_e ≃ φ_{F(e)}
 * 
 * A syntactic Quine is a self-reproducing expression Q whose evaluation
 * produces its own source representation:
 *     eval(Q) ≡ repr(Q)
 * 
 * Anti-Triviality Constraint:
 * Circular definitions such as `type Q = Q;` are prohibited and trigger TS2456.
 * The quine must synthesize its own representation dynamically through the
 * diagonal application of an operator to its own quotation:
 *     δ(x) = App(x, Quote(x))
 *     Q = App(Diag, Quote(Diag))
 * 
 * During evaluation:
 *     Resolve<Q> 
 *   = Resolve<App<Diag, Quote(Diag)>>
 *   = App(Resolve<Quote<Diag>>, Quote(Resolve<Quote<Diag>>))
 *   = App(Diag, Quote(Diag))
 *   = Q
 */

import { Equal } from './assertions';

// ============================================================================
// Abstract Syntax Tree (AST) Universe
// ============================================================================

export interface AstQuote<T> {
  readonly _tag: 'Quote';
  readonly value: T;
}

export interface AstApp<Fn, Arg> {
  readonly _tag: 'App';
  readonly fn: Fn;
  readonly arg: Arg;
}

export interface AstPair<First, Second> {
  readonly _tag: 'Pair';
  readonly first: First;
  readonly second: Second;
}

export interface AstConst<T> {
  readonly _tag: 'Const';
  readonly value: T;
}

export interface AstDiag {
  readonly _tag: 'Diag';
}

export interface AstIdentity {
  readonly _tag: 'Identity';
}

export type AstNode =
  | AstQuote<unknown>
  | AstApp<unknown, unknown>
  | AstPair<unknown, unknown>
  | AstConst<unknown>
  | AstDiag
  | AstIdentity;

// Helper constructors
export type Quote<T> = { readonly _tag: 'Quote'; readonly value: T };
export type App<Fn, Arg> = { readonly _tag: 'App'; readonly fn: Fn; readonly arg: Arg };
export type Pair<F, S> = { readonly _tag: 'Pair'; readonly first: F; readonly second: S };
export type Const<T> = { readonly _tag: 'Const'; readonly value: T };
export type Diag = { readonly _tag: 'Diag' };
export type Identity = { readonly _tag: 'Identity' };

// ============================================================================
// Type-Level Evaluator / Reducer: Resolve<Expr>
// ============================================================================

/**
 * Evaluates an AST expression according to standard call-by-value / term reduction.
 */
export type Resolve<Expr> =
  // 1. Quotation: returns the quoted payload untouched (evaluation barrier)
  Expr extends { readonly _tag: 'Quote'; readonly value: infer V }
    ? V
  // 2. Identity: returns its argument
  : Expr extends { readonly _tag: 'App'; readonly fn: { readonly _tag: 'Identity' }; readonly arg: infer A }
    ? Resolve<A>
  // 3. Diagonalization Operator δ(x) = App(x, Quote(x)):
  // Takes argument x (resolved), and synthesizes App<x, Quote<x>>
  : Expr extends { readonly _tag: 'App'; readonly fn: { readonly _tag: 'Diag' }; readonly arg: infer A }
    ? Resolve<A> extends infer EvaluatedArg
      ? {
          readonly _tag: 'App';
          readonly fn: EvaluatedArg;
          readonly arg: {
            readonly _tag: 'Quote';
            readonly value: EvaluatedArg;
          };
        }
      : never
  // 4. General application: resolve operator and argument
  : Expr extends { readonly _tag: 'App'; readonly fn: infer F; readonly arg: infer A }
    ? Resolve<F> extends infer EvaluatedFn
      ? Resolve<{ readonly _tag: 'App'; readonly fn: EvaluatedFn; readonly arg: A }>
      : never
  // 5. Pairs: resolve both components
  : Expr extends { readonly _tag: 'Pair'; readonly first: infer F; readonly second: infer S }
    ? {
        readonly _tag: 'Pair';
        readonly first: Resolve<F>;
        readonly second: Resolve<S>;
      }
  // 6. Constants & Atoms: return as-is
  : Expr;

// ============================================================================
// The Kleene Quine
// ============================================================================

/**
 * The Quine expression: Q = App<Diag, Quote<Diag>>
 * 
 * Note that this definition contains ZERO circular references.
 * Neither Diag nor Quote<Diag> refers to Quine.
 */
export type Quine = {
  readonly _tag: 'App';
  readonly fn: Diag;
  readonly arg: {
    readonly _tag: 'Quote';
    readonly value: Diag;
  };
};

/**
 * Expected AST output of evaluating the Quine.
 */
export type QuineAst = {
  readonly _tag: 'App';
  readonly fn: Diag;
  readonly arg: {
    readonly _tag: 'Quote';
    readonly value: Diag;
  };
};

// ============================================================================
// Compile-Time Serializer / Pretty Printer: PrintAst<T>
// ============================================================================

export type PrintAst<Node> =
  Node extends { readonly _tag: 'Diag' }
    ? 'Diag'
  : Node extends { readonly _tag: 'Identity' }
    ? 'Id'
  : Node extends { readonly _tag: 'Quote'; readonly value: infer V }
    ? `Quote(${PrintAst<V>})`
  : Node extends { readonly _tag: 'App'; readonly fn: infer F; readonly arg: infer A }
    ? `App(${PrintAst<F>}, ${PrintAst<A>})`
  : Node extends { readonly _tag: 'Pair'; readonly first: infer F; readonly second: infer S }
    ? `Pair(${PrintAst<F>}, ${PrintAst<S>})`
  : Node extends { readonly _tag: 'Const'; readonly value: infer V }
    ? `Const(${V extends string | number | boolean ? `${V}` : '?'})`
  : 'Unknown';
