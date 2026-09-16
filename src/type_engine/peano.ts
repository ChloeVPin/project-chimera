/**
 * Project Chimera: Peano Arithmetic & Non-Primitive Recursive Growth (Ackermann Engine)
 * 
 * Formal Specification:
 * Let N be the set of natural numbers represented as unary tuple types:
 * 0 = []
 * S(n) = [unknown, ...n]
 * 
 * Addition:
 *   Add<M, N> = [...M, ...N]  (O(1) in TypeScript's tuple spread)
 * 
 * Multiplication:
 *   Mul<M, N> = recursive concatenation (O(M * N))
 * 
 * Ackermann-Péter Function:
 *   A(0, n) = n + 1
 *   A(m, 0) = A(m - 1, 1)
 *   A(m, n) = A(m - 1, A(m, n - 1))
 * 
 * A(m, n) is famous for being non-primitive recursive. Even tiny arguments
 * (e.g. A(3, 4) = 125, A(4, 1) = 65533, A(4, 2) = 2^65536 - 3) probe the
 * extreme limits of stack depth, memoization tables, and circuit breakers.
 */

export type Zero = [];
export type Succ<N extends readonly unknown[]> = [unknown, ...N];
export type Prev<N extends readonly unknown[]> = N extends [unknown, ...infer Rest] ? Rest : [];

// Peano conversion utilities:
export type NatToPeano<N extends number, Acc extends readonly unknown[] = []> =
  Acc['length'] extends N
    ? Acc
    : NatToPeano<N, Succ<Acc>>;

export type PeanoToNat<P extends readonly unknown[]> = P['length'];

// Addition: O(1) tuple expansion
export type Add<A extends readonly unknown[], B extends readonly unknown[]> = [...A, ...B];

// Multiplication:
export type Mul<
  A extends readonly unknown[],
  B extends readonly unknown[],
  Acc extends readonly unknown[] = []
> = A extends [unknown, ...infer Tail]
  ? Mul<Tail, B, [...Acc, ...B]>
  : Acc;

/**
 * Type-level Ackermann function.
 * Note: TypeScript conditional recursion will evaluate nested expressions.
 */
export type Ackermann<
  M extends readonly unknown[],
  N extends readonly unknown[]
> = M extends []
  ? Succ<N>
  : N extends []
    ? Prev<M> extends infer MPrev extends readonly unknown[]
      ? Ackermann<MPrev, Succ<[]>>
      : never
    : Prev<M> extends infer MPrev extends readonly unknown[]
      ? Prev<N> extends infer NPrev extends readonly unknown[]
        ? Ackermann<M, NPrev> extends infer Inner extends readonly unknown[]
          ? Ackermann<MPrev, Inner>
          : never
        : never
      : never;
