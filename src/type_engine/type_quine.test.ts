/**
 * Project Chimera: Type-Level Quine Verification Suite
 * 
 * Verifies Kleene's Second Recursion Theorem within TypeScript's type system:
 * 1. Self-reproduction: Resolve<Quine> evaluates to QuineAst.
 * 2. Structural identity: Resolve<Quine> ≡ Quine.
 * 3. Fixed-point idempotency: Resolve^k(Quine) ≡ Quine for all k >= 1.
 * 4. Serialized isomorphism: PrintAst<Resolve<Quine>> ≡ "App(Diag, Quote(Diag))".
 * 5. General interpreter validity: Verifies Quote, Identity, Diag, and Pair mechanics.
 */

import { Equal, staticAssert } from './assertions';
import {
  Resolve,
  Quine,
  QuineAst,
  PrintAst,
  App,
  Quote,
  Diag,
  Identity,
  Pair,
  Const
} from './type_quine';

// ============================================================================
// Primary Deliverable Proof: Kleene's Second Recursion Theorem
// ============================================================================

// 1. Quine evaluation produces its exact AST representation
type EvaluatedQuine = Resolve<Quine>;
staticAssert<Equal<EvaluatedQuine, QuineAst>>();

// 2. Syntactic self-reproduction: The evaluated form equals the original expression
staticAssert<Equal<EvaluatedQuine, Quine>>();

// 3. Fixed-point idempotency: Evaluating the quine multiple times remains stable
type QuineOrder2 = Resolve<Resolve<Quine>>;
staticAssert<Equal<QuineOrder2, QuineAst>>();

type QuineOrder3 = Resolve<Resolve<Resolve<Quine>>>;
staticAssert<Equal<QuineOrder3, QuineAst>>();

// 4. Serialized template literal representation match
type SerializedOutput = PrintAst<EvaluatedQuine>;
type ExpectedSerialized = 'App(Diag, Quote(Diag))';
staticAssert<Equal<SerializedOutput, ExpectedSerialized>>();

type SerializedSource = PrintAst<Quine>;
staticAssert<Equal<SerializedSource, ExpectedSerialized>>();
staticAssert<Equal<SerializedOutput, SerializedSource>>();

// ============================================================================
// Auxiliary Evaluator Proofs (Ensuring Non-Trivial General Evaluation)
// ============================================================================

// Quotation barrier test: Quote<T> resolves to T
type QuotedTest = Resolve<Quote<Const<42>>>;
staticAssert<Equal<QuotedTest, Const<42>>>();

// Identity application test: App<Identity, Const<99>> resolves to Const<99>
type IdentityTest = Resolve<App<Identity, Const<99>>>;
staticAssert<Equal<IdentityTest, Const<99>>>();

// Diag application on non-quine argument:
// Diag(Identity) resolves to App<Identity, Quote<Identity>>
type DiagTest = Resolve<App<Diag, Quote<Identity>>>;
type ExpectedDiagTest = App<Identity, Quote<Identity>>;
staticAssert<Equal<DiagTest, ExpectedDiagTest>>();

// Pair evaluation test
type PairTest = Resolve<Pair<App<Identity, Const<1>>, Quote<Const<2>>>>;
type ExpectedPairTest = {
  readonly _tag: 'Pair';
  readonly first: Const<1>;
  readonly second: Const<2>;
};
staticAssert<Equal<PairTest, ExpectedPairTest>>();
