/**
 * Project Chimera: Verification Suite for Pure Type-Level Brainfuck Engine
 * 
 * All tests execute purely during type checking.
 * Verified with zero runtime footprint.
 */

import { Equal, staticAssert } from './assertions';
import { BrainfuckResult, RunBrainfuck, Tokenize } from './brainfuck';

// ============================================================================
// Test Vector 1: Tokenizer & AST Filtering
// ============================================================================

type SourceWithComments = '++ // increment\n > +++ // move right';
type Tokens = Tokenize<SourceWithComments>;
staticAssert<Equal<Tokens, ['+', '+', '>', '+', '+', '+']>>();

// ============================================================================
// Test Vector 2: Basic Arithmetic and Cell Clearance
// ============================================================================

// 5 - 5 = 0 via loop
type ClearProg = '+++++[-]';
type ClearResult = BrainfuckResult<ClearProg>;
staticAssert<Equal<ClearResult, 0>>();

// ============================================================================
// Test Vector 3: Addition (3 + 5 = 8)
// Program:
//   Cell 0 = 3 (+++)
//   Cell 1 = 5 (>+++++)
//   Loop: [<+>-] (add cell 1 into cell 0)
//   Move back to cell 0 (<)
// ============================================================================

type Add3Plus5 = '+++>+++++[<+>-]<';
type AddResult = BrainfuckResult<Add3Plus5>;
staticAssert<Equal<AddResult, 8>>();

// Addition 4 + 7 = 11
type Add4Plus7 = '++++>+++++++[<+>-]<';
type AddResult11 = BrainfuckResult<Add4Plus7>;
staticAssert<Equal<AddResult11, 11>>();

// ============================================================================
// Test Vector 4: Subtraction (7 - 3 = 4)
// Program:
//   Cell 0 = 7 (+++++++)
//   Cell 1 = 3 (>+++)
//   Loop: [<->-] (decrement cell 0 for each cell 1)
//   Move back to cell 0 (<)
// ============================================================================

type Sub7Minus3 = '+++++++>+++[<->-]<';
type SubResult = BrainfuckResult<Sub7Minus3>;
staticAssert<Equal<SubResult, 4>>();

// ============================================================================
// Test Vector 5: Multiplication (3 * 4 = 12)
// Program:
//   Cell 0 = 3 (+++)
//   Cell 1 = 4 (>++++<)
//   Nested loop multiplication:
//     [>[>+>+<<-]>>[<<+>>-]<<<-]>>
//   Cell 2 accumulates product 12.
// ============================================================================

type Mul3Times4 = '+++>++++<[>[>+>+<<-]>>[<<+>>-]<<<-]>>';
type MulResult = BrainfuckResult<Mul3Times4>;
staticAssert<Equal<MulResult, 12>>();

// Multiplication 2 * 5 = 10
type Mul2Times5 = '++>+++++<[>[>+>+<<-]>>[<<+>>-]<<<-]>>';
type MulResult10 = BrainfuckResult<Mul2Times5>;
staticAssert<Equal<MulResult10, 10>>();
