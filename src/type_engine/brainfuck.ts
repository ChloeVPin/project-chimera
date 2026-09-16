/**
 * Project Chimera: Phase 7 - Pure Type-Level Brainfuck Computational Engine
 * 
 * Formal Operational Semantics:
 * Brainfuck is an ultra-minimal, 8-instruction Turing-complete imperative programming language:
 *   Σ_BF = { '+', '-', '<', '>', '[', ']' }
 * 
 * Turing Machine State Tuple:
 *   M = (Tape_L, Cell_curr, Tape_R, Program_AST)
 * 
 * Data Tape Representation (Zipper Data Structure):
 *   A bi-infinite tape of natural numbers is represented as two stacks (Left, Right)
 *   and a focused Current element:
 *     ... | L_2 | L_1 | [ Curr ] | R_1 | R_2 | ...
 * 
 * Operational Rules:
 *   '+'  : Curr' = Curr + 1
 *   '-'  : Curr' = max(0, Curr - 1)
 *   '>'  : Left' = [Curr, ...Left], Curr' = Head(Right), Right' = Tail(Right)
 *   '<'  : Right' = [Curr, ...Right], Curr' = Head(Left), Left' = Tail(Left)
 *   '['  : If Curr == 0, skip to matching ']'; else enter loop body.
 *   ']'  : If Curr != 0, return to matching '['; else exit loop.
 * 
 * In this implementation, the program is parsed at COMPILE TIME into a structured
 * Abstract Syntax Tree (AST), resolving loop bracket balancing prior to evaluation.
 * No runtime JavaScript is generated.
 */

// ============================================================================
// Inductive Peano Number Representation
// ============================================================================

export type Peano = readonly unknown[];
export type Zero = [];
export type Succ<N extends Peano> = [unknown, ...N];
export type Pred<N extends Peano> = N extends [unknown, ...infer Rest] ? Rest : [];

export type PeanoToNat<N extends Peano> = N['length'];

export type NatToPeano<N extends number, Acc extends Peano = []> =
  Acc['length'] extends N
    ? Acc
    : NatToPeano<N, Succ<Acc>>;

// ============================================================================
// Tape Zipper Functional Data Structure
// ============================================================================

export interface Tape<
  Left extends readonly Peano[] = [],
  Curr extends Peano = Zero,
  Right extends readonly Peano[] = []
> {
  readonly left: Left;
  readonly curr: Curr;
  readonly right: Right;
}

export type EmptyTape = Tape<[], Zero, []>;

export type TapeInc<T extends Tape<any, any, any>> = Tape<T['left'], Succ<T['curr']>, T['right']>;
export type TapeDec<T extends Tape<any, any, any>> = Tape<T['left'], Pred<T['curr']>, T['right']>;

export type MoveLeft<T extends Tape<any, any, any>> =
  T['left'] extends [infer L extends Peano, ...infer RestL extends readonly Peano[]]
    ? Tape<RestL, L, [T['curr'], ...T['right']]>
    : Tape<[], Zero, [T['curr'], ...T['right']]>;

export type MoveRight<T extends Tape<any, any, any>> =
  T['right'] extends [infer R extends Peano, ...infer RestR extends readonly Peano[]]
    ? Tape<[T['curr'], ...T['left']], R, RestR>
    : Tape<[T['curr'], ...T['left']], Zero, []>;

// ============================================================================
// Compile-Time Lexer & AST Parser
// ============================================================================

export type BrainfuckOp = '+' | '-' | '<' | '>';

export interface LoopNode<Body extends readonly ASTNode[]> {
  readonly kind: 'loop';
  readonly body: Body;
}

export type ASTNode = BrainfuckOp | LoopNode<readonly any[]>;

/**
 * Tokenizer: Extracts valid Brainfuck instructions from string literals.
 * Filters out whitespace and comment characters.
 */
export type Tokenize<S extends string, Acc extends readonly string[] = []> =
  S extends `${infer Char}${infer Rest}`
    ? Char extends '+' | '-' | '<' | '>' | '[' | ']'
      ? Tokenize<Rest, [...Acc, Char]>
      : Tokenize<Rest, Acc>
    : Acc;

/**
 * Recursive Descent Bracket Parser:
 * Constructs nested AST nodes for balanced loop blocks.
 */
export type ParseLoop<
  Tokens extends readonly string[],
  Acc extends readonly ASTNode[] = []
> = Tokens extends [infer Head, ...infer Tail extends readonly string[]]
  ? Head extends ']'
    ? { readonly node: LoopNode<Acc>; readonly rest: Tail }
    : Head extends '['
      ? ParseLoop<Tail, []> extends { readonly node: infer ChildNode extends ASTNode; readonly rest: infer RestTokens extends readonly string[] }
        ? ParseLoop<RestTokens, [...Acc, ChildNode]>
        : never
      : Head extends BrainfuckOp
        ? ParseLoop<Tail, [...Acc, Head]>
        : never
  : { readonly node: LoopNode<Acc>; readonly rest: [] };

export type ParseProgram<
  Tokens extends readonly string[],
  Acc extends readonly ASTNode[] = []
> = Tokens extends [infer Head, ...infer Tail extends readonly string[]]
  ? Head extends '['
    ? ParseLoop<Tail, []> extends { readonly node: infer ChildNode extends ASTNode; readonly rest: infer RestTokens extends readonly string[] }
      ? ParseProgram<RestTokens, [...Acc, ChildNode]>
      : never
    : Head extends BrainfuckOp
      ? ParseProgram<Tail, [...Acc, Head]>
      : never
  : Acc;

// ============================================================================
// Virtual Machine Evaluator
// ============================================================================

export type EvalNode<Node extends ASTNode, T extends Tape<any, any, any>> =
  Node extends '+' ? TapeInc<T> :
  Node extends '-' ? TapeDec<T> :
  Node extends '<' ? MoveLeft<T> :
  Node extends '>' ? MoveRight<T> :
  Node extends LoopNode<infer Body extends readonly ASTNode[]> ? EvalLoop<Body, T> :
  T;

export type EvalLoop<
  Body extends readonly ASTNode[],
  T extends Tape<any, any, any>
> = T['curr'] extends Zero
  ? T
  : EvalBlock<Body, T> extends infer NextTape extends Tape<any, any, any>
    ? EvalLoop<Body, NextTape>
    : never;

export type EvalBlock<
  Nodes extends readonly ASTNode[],
  T extends Tape<any, any, any>
> = Nodes extends [infer Head extends ASTNode, ...infer Tail extends readonly ASTNode[]]
  ? EvalNode<Head, T> extends infer NextT extends Tape<any, any, any>
    ? EvalBlock<Tail, NextT>
    : never
  : T;

// ============================================================================
// High-Level User Interfaces
// ============================================================================

/**
 * Complete Execution Pipeline:
 * Tokenize -> Parse AST -> Evaluate on Zipper Tape.
 */
export type RunBrainfuck<Code extends string> =
  ParseProgram<Tokenize<Code>> extends infer AST extends readonly ASTNode[]
    ? EvalBlock<AST, EmptyTape>
    : never;

/**
 * Returns the numerical scalar value at the current tape head.
 */
export type BrainfuckResult<Code extends string> =
  RunBrainfuck<Code> extends infer FinalState extends Tape<any, any, any>
    ? PeanoToNat<FinalState['curr']>
    : never;
