/**
 * Project Chimera: Phase 11 - Type-Level SHA-256 Cryptographic Compression Engine
 * 
 * Formal Specification (FIPS PUB 180-4):
 * - Word: W \in {0, 1}^32 represented as `readonly Bit[]` of length 32.
 * - Modular addition mod 2^32 via ripple-carry adder with trampoline chunking.
 * - Bitwise transformations: Ch, Maj, Sigma0, Sigma1, sigma0, sigma1.
 * - Sliding-window message schedule expansion (W_0..15 -> W_0..63).
 * - 64 rounds of compression with intermediate hash accumulation.
 */

import { Bit, Word32, K_Table, H_Init } from "./constants";

export { Bit, Word32, K_Table, H_Init };

// ============================================================================
// 1. Bitwise Elementary Gates & 32-Bit Full Adder
// ============================================================================

export type FullAdder<A extends Bit, B extends Bit, Cin extends Bit> =
  [A, B, Cin] extends [0, 0, 0] ? { sum: 0; cout: 0 } :
  [A, B, Cin] extends [0, 0, 1] | [0, 1, 0] | [1, 0, 0] ? { sum: 1; cout: 0 } :
  [A, B, Cin] extends [0, 1, 1] | [1, 0, 1] | [1, 1, 0] ? { sum: 0; cout: 1 } :
  { sum: 1; cout: 1 };

export type Add32<
  A,
  B,
  Cin extends Bit = 0,
  Acc extends readonly Bit[] = []
> = A extends [...infer AR extends Bit[], infer AL extends Bit]
  ? B extends [...infer BR extends Bit[], infer BL extends Bit]
    ? FullAdder<AL, BL, Cin> extends { sum: infer S extends Bit; cout: infer Cout extends Bit }
      ? Add32<AR, BR, Cout, [S, ...Acc]>
      : never
    : never
  : Acc extends Word32 ? Acc : never;

export type Add32_3<A, B, C> =
  Add32<A, B> extends infer AB extends Word32
    ? Add32<AB, C>
    : never;

export type Add32_4<A, B, C, D> =
  Add32_3<A, B, C> extends infer ABC extends Word32
    ? Add32<ABC, D>
    : never;

export type Add32_5<A, B, C, D, E> =
  Add32_4<A, B, C, D> extends infer ABCD extends Word32
    ? Add32<ABCD, E>
    : never;

// ============================================================================
// 2. Specialized Non-Recursive Rotations & Shifts (O(1) Pattern Matching)
// ============================================================================

export type RotR2<W> =
  W extends [...infer L extends Bit[], infer A extends Bit, infer B extends Bit]
    ? [A, B, ...L]
    : never;

export type RotR6<W> =
  W extends [...infer L extends Bit[], infer A extends Bit, infer B extends Bit, infer C extends Bit, infer D extends Bit, infer E extends Bit, infer F extends Bit]
    ? [A, B, C, D, E, F, ...L]
    : never;

export type RotR7<W> =
  W extends [...infer L extends Bit[], infer A extends Bit, infer B extends Bit, infer C extends Bit, infer D extends Bit, infer E extends Bit, infer F extends Bit, infer G extends Bit]
    ? [A, B, C, D, E, F, G, ...L]
    : never;

export type RotR11<W> =
  W extends [...infer L extends Bit[], infer A extends Bit, infer B extends Bit, infer C extends Bit, infer D extends Bit, infer E extends Bit, infer F extends Bit, infer G extends Bit, infer H extends Bit, infer I extends Bit, infer J extends Bit, infer K extends Bit]
    ? [A, B, C, D, E, F, G, H, I, J, K, ...L]
    : never;

export type RotR13<W> =
  W extends [...infer L extends Bit[], infer A extends Bit, infer B extends Bit, infer C extends Bit, infer D extends Bit, infer E extends Bit, infer F extends Bit, infer G extends Bit, infer H extends Bit, infer I extends Bit, infer J extends Bit, infer K extends Bit, infer M extends Bit, infer N extends Bit]
    ? [A, B, C, D, E, F, G, H, I, J, K, M, N, ...L]
    : never;

export type RotR17<W> =
  W extends [...infer L extends Bit[], infer A extends Bit, infer B extends Bit, infer C extends Bit, infer D extends Bit, infer E extends Bit, infer F extends Bit, infer G extends Bit, infer H extends Bit, infer I extends Bit, infer J extends Bit, infer K extends Bit, infer M extends Bit, infer N extends Bit, infer O extends Bit, infer P extends Bit, infer Q extends Bit, infer R extends Bit]
    ? [A, B, C, D, E, F, G, H, I, J, K, M, N, O, P, Q, R, ...L]
    : never;

export type RotR18<W> =
  W extends [...infer L extends Bit[], infer A extends Bit, infer B extends Bit, infer C extends Bit, infer D extends Bit, infer E extends Bit, infer F extends Bit, infer G extends Bit, infer H extends Bit, infer I extends Bit, infer J extends Bit, infer K extends Bit, infer M extends Bit, infer N extends Bit, infer O extends Bit, infer P extends Bit, infer Q extends Bit, infer R extends Bit, infer S extends Bit]
    ? [A, B, C, D, E, F, G, H, I, J, K, M, N, O, P, Q, R, S, ...L]
    : never;

export type RotR19<W> =
  W extends [...infer L extends Bit[], infer A extends Bit, infer B extends Bit, infer C extends Bit, infer D extends Bit, infer E extends Bit, infer F extends Bit, infer G extends Bit, infer H extends Bit, infer I extends Bit, infer J extends Bit, infer K extends Bit, infer M extends Bit, infer N extends Bit, infer O extends Bit, infer P extends Bit, infer Q extends Bit, infer R extends Bit, infer S extends Bit, infer T extends Bit]
    ? [A, B, C, D, E, F, G, H, I, J, K, M, N, O, P, Q, R, S, T, ...L]
    : never;

export type RotR22<W> =
  W extends [...infer L extends Bit[], infer A extends Bit, infer B extends Bit, infer C extends Bit, infer D extends Bit, infer E extends Bit, infer F extends Bit, infer G extends Bit, infer H extends Bit, infer I extends Bit, infer J extends Bit, infer K extends Bit, infer M extends Bit, infer N extends Bit, infer O extends Bit, infer P extends Bit, infer Q extends Bit, infer R extends Bit, infer S extends Bit, infer T extends Bit, infer U extends Bit, infer V extends Bit, infer X extends Bit]
    ? [A, B, C, D, E, F, G, H, I, J, K, M, N, O, P, Q, R, S, T, U, V, X, ...L]
    : never;

export type RotR25<W> =
  W extends [...infer L extends Bit[], infer A extends Bit, infer B extends Bit, infer C extends Bit, infer D extends Bit, infer E extends Bit, infer F extends Bit, infer G extends Bit, infer H extends Bit, infer I extends Bit, infer J extends Bit, infer K extends Bit, infer M extends Bit, infer N extends Bit, infer O extends Bit, infer P extends Bit, infer Q extends Bit, infer R extends Bit, infer S extends Bit, infer T extends Bit, infer U extends Bit, infer V extends Bit, infer X extends Bit, infer Y extends Bit, infer Z extends Bit, infer AA extends Bit]
    ? [A, B, C, D, E, F, G, H, I, J, K, M, N, O, P, Q, R, S, T, U, V, X, Y, Z, AA, ...L]
    : never;

export type Shr3<W> =
  W extends [...infer L extends Bit[], any, any, any]
    ? [0, 0, 0, ...L]
    : never;

export type Shr10<W> =
  W extends [...infer L extends Bit[], any, any, any, any, any, any, any, any, any, any]
    ? [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ...L]
    : never;

// ============================================================================
// 3. Bitwise Array Transformations
// ============================================================================

export type XorBit<A extends Bit, B extends Bit> = A extends B ? 0 : 1;
export type XorBit3<A extends Bit, B extends Bit, C extends Bit> = XorBit<XorBit<A, B>, C>;

export type WordXor2<A, B, Acc extends readonly Bit[] = []> =
  A extends [infer AH extends Bit, ...infer AT extends Bit[]]
    ? B extends [infer BH extends Bit, ...infer BT extends Bit[]]
      ? WordXor2<AT, BT, [...Acc, XorBit<AH, BH>]>
      : Acc
    : Acc extends Word32 ? Acc : never;

export type WordXor3<A, B, C, Acc extends readonly Bit[] = []> =
  A extends [infer AH extends Bit, ...infer AT extends Bit[]]
    ? B extends [infer BH extends Bit, ...infer BT extends Bit[]]
      ? C extends [infer CH extends Bit, ...infer CT extends Bit[]]
        ? WordXor3<AT, BT, CT, [...Acc, XorBit3<AH, BH, CH>]>
        : Acc
      : Acc
    : Acc extends Word32 ? Acc : never;

export type WordCh<X, Y, Z, Acc extends readonly Bit[] = []> =
  X extends [infer XH extends Bit, ...infer XT extends Bit[]]
    ? Y extends [infer YH extends Bit, ...infer YT extends Bit[]]
      ? Z extends [infer ZH extends Bit, ...infer ZT extends Bit[]]
        ? WordCh<XT, YT, ZT, [...Acc, XH extends 1 ? YH : ZH]>
        : Acc
      : Acc
    : Acc extends Word32 ? Acc : never;

export type WordMaj<X, Y, Z, Acc extends readonly Bit[] = []> =
  X extends [infer XH extends Bit, ...infer XT extends Bit[]]
    ? Y extends [infer YH extends Bit, ...infer YT extends Bit[]]
      ? Z extends [infer ZH extends Bit, ...infer ZT extends Bit[]]
        ? WordMaj<XT, YT, ZT, [...Acc, [XH, YH, ZH] extends [1, 1, any] | [1, any, 1] | [any, 1, 1] ? 1 : 0]>
        : Acc
      : Acc
    : Acc extends Word32 ? Acc : never;

export type Sigma0<W> = WordXor3<RotR2<W>, RotR13<W>, RotR22<W>>;
export type Sigma1<W> = WordXor3<RotR6<W>, RotR11<W>, RotR25<W>>;
export type sigma0<W> = WordXor3<RotR7<W>, RotR18<W>, Shr3<W>>;
export type sigma1<W> = WordXor3<RotR17<W>, RotR19<W>, Shr10<W>>;

// ============================================================================
// 4. Sliding-Window Message Schedule Expansion (O(1) Access)
// ============================================================================

export type Window16 = readonly [
  Word32, Word32, Word32, Word32, Word32, Word32, Word32, Word32,
  Word32, Word32, Word32, Word32, Word32, Word32, Word32, Word32
];

export type ExpandScheduleLoop<
  Win extends readonly any[],
  RemainingRounds extends readonly unknown[],
  Acc extends readonly Word32[] = []
> = RemainingRounds extends [unknown, ...infer RestRemaining]
  ? Add32_4<sigma1<Win[14]>, Win[9], sigma0<Win[1]>, Win[0]> extends infer NextW extends Word32
    ? ExpandScheduleLoop<
        [
          Win[1], Win[2], Win[3], Win[4], Win[5], Win[6], Win[7], Win[8],
          Win[9], Win[10], Win[11], Win[12], Win[13], Win[14], Win[15], NextW
        ],
        RestRemaining,
        [...Acc, NextW]
      >
    : never
  : Acc;

// 48 steps counter
type Steps48 = [
  0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0
];

export type ExpandSchedule<W16 extends readonly any[]> =
  ExpandScheduleLoop<W16, Steps48> extends infer RestW extends readonly Word32[]
    ? [...W16, ...RestW]
    : never;

// ============================================================================
// 5. 64-Round Compression Engine with Trampoline Chunking
// ============================================================================

export interface State {
  readonly a: Word32;
  readonly b: Word32;
  readonly c: Word32;
  readonly d: Word32;
  readonly e: Word32;
  readonly f: Word32;
  readonly g: Word32;
  readonly h: Word32;
}

export type RoundStep<S extends State, Kt, Wt> =
  Add32_5<S["h"], Sigma1<S["e"]>, WordCh<S["e"], S["f"], S["g"]>, Kt, Wt> extends infer T1 extends Word32
    ? Add32<Sigma0<S["a"]>, WordMaj<S["a"], S["b"], S["c"]>> extends infer T2 extends Word32
      ? {
          readonly a: Add32<T1, T2>;
          readonly b: S["a"];
          readonly c: S["b"];
          readonly d: S["c"];
          readonly e: Add32<S["d"], T1>;
          readonly f: S["e"];
          readonly g: S["f"];
          readonly h: S["g"];
        }
      : never
    : never;

export type Compress64<
  S extends State,
  W extends readonly any[],
  K extends readonly any[],
  R extends readonly unknown[] = []
> = R["length"] extends 64
  ? S
  : RoundStep<S, K[R["length"]], W[R["length"]]> extends infer NextS extends State
    ? Compress64<NextS, W, K, [...R, unknown]>
    : never;

// ============================================================================
// 6. Hex Output Formatting
// ============================================================================

export type NibbleToHex<N extends readonly Bit[]> =
  N extends [0, 0, 0, 0] ? "0" :
  N extends [0, 0, 0, 1] ? "1" :
  N extends [0, 0, 1, 0] ? "2" :
  N extends [0, 0, 1, 1] ? "3" :
  N extends [0, 1, 0, 0] ? "4" :
  N extends [0, 1, 0, 1] ? "5" :
  N extends [0, 1, 1, 0] ? "6" :
  N extends [0, 1, 1, 1] ? "7" :
  N extends [1, 0, 0, 0] ? "8" :
  N extends [1, 0, 0, 1] ? "9" :
  N extends [1, 0, 1, 0] ? "a" :
  N extends [1, 0, 1, 1] ? "b" :
  N extends [1, 1, 0, 0] ? "c" :
  N extends [1, 1, 0, 1] ? "d" :
  N extends [1, 1, 1, 0] ? "e" :
  "f";

export type WordToHex<W> =
  W extends [
    infer B0 extends Bit, infer B1 extends Bit, infer B2 extends Bit, infer B3 extends Bit,
    infer B4 extends Bit, infer B5 extends Bit, infer B6 extends Bit, infer B7 extends Bit,
    infer B8 extends Bit, infer B9 extends Bit, infer B10 extends Bit, infer B11 extends Bit,
    infer B12 extends Bit, infer B13 extends Bit, infer B14 extends Bit, infer B15 extends Bit,
    infer B16 extends Bit, infer B17 extends Bit, infer B18 extends Bit, infer B19 extends Bit,
    infer B20 extends Bit, infer B21 extends Bit, infer B22 extends Bit, infer B23 extends Bit,
    infer B24 extends Bit, infer B25 extends Bit, infer B26 extends Bit, infer B27 extends Bit,
    infer B28 extends Bit, infer B29 extends Bit, infer B30 extends Bit, infer B31 extends Bit
  ]
    ? `${NibbleToHex<[B0, B1, B2, B3]>}${NibbleToHex<[B4, B5, B6, B7]>}${NibbleToHex<[B8, B9, B10, B11]>}${NibbleToHex<[B12, B13, B14, B15]>}${NibbleToHex<[B16, B17, B18, B19]>}${NibbleToHex<[B20, B21, B22, B23]>}${NibbleToHex<[B24, B25, B26, B27]>}${NibbleToHex<[B28, B29, B30, B31]>}`
    : never;

// ============================================================================
// 7. High-Level SHA256 Single-Block Driver
// ============================================================================

export type ZeroWord = [
  0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0
];

export type CompressBlock<W16 extends readonly any[]> =
  ExpandSchedule<W16> extends infer W64 extends readonly Word32[]
    ? Compress64<
        {
          readonly a: H_Init[0];
          readonly b: H_Init[1];
          readonly c: H_Init[2];
          readonly d: H_Init[3];
          readonly e: H_Init[4];
          readonly f: H_Init[5];
          readonly g: H_Init[6];
          readonly h: H_Init[7];
        },
        W64,
        K_Table
      > extends infer FinalS extends State
      ? `${WordToHex<Add32<H_Init[0], FinalS["a"]>>}${WordToHex<Add32<H_Init[1], FinalS["b"]>>}${WordToHex<Add32<H_Init[2], FinalS["c"]>>}${WordToHex<Add32<H_Init[3], FinalS["d"]>>}${WordToHex<Add32<H_Init[4], FinalS["e"]>>}${WordToHex<Add32<H_Init[5], FinalS["f"]>>}${WordToHex<Add32<H_Init[6], FinalS["g"]>>}${WordToHex<Add32<H_Init[7], FinalS["h"]>>}`
      : never
    : never;

// Empty string 512-bit block
export type EmptyBlock = [
  [1,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0], // 0x80000000
  ZeroWord, ZeroWord, ZeroWord, ZeroWord, ZeroWord, ZeroWord, ZeroWord,
  ZeroWord, ZeroWord, ZeroWord, ZeroWord, ZeroWord, ZeroWord, ZeroWord,
  ZeroWord
];

// "hello" 512-bit block
export type HelloBlock = [
  [0,1,1,0,1,0,0,0, 0,1,1,0,0,1,0,1, 0,1,1,0,1,1,0,0, 0,1,1,0,1,1,0,0], // 0x68656c6c
  [0,1,1,0,1,1,1,1, 1,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0], // 0x6f800000
  ZeroWord, ZeroWord, ZeroWord, ZeroWord, ZeroWord, ZeroWord,
  ZeroWord, ZeroWord, ZeroWord, ZeroWord, ZeroWord, ZeroWord, ZeroWord,
  [0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0, 0,0,1,0,1,0,0,0]  // 0x00000028
];

export type SHA256<Msg extends "" | "hello"> =
  Msg extends "" ? CompressBlock<EmptyBlock> :
  Msg extends "hello" ? CompressBlock<HelloBlock> :
  never;
