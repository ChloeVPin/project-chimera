/**
 * Project Chimera: Phase 11 - Type-Level SHA-256 Verification Proofs
 * 
 * Verifies NIST test vectors strictly at compile time with zero runtime JavaScript:
 * 1. Empty string hash:
 *    SHA256<""> == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
 * 2. "hello" string hash:
 *    SHA256<"hello"> == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
 */

import { Equal, staticAssert } from "../type_engine/assertions";
import { SHA256 } from "./sha256";

// ============================================================================
// Primary NIST Verification Proofs
// ============================================================================

// 1. Empty Message Verification
export type HashEmpty = SHA256<"">;
export type ExpectedEmptyHash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
staticAssert<Equal<HashEmpty, ExpectedEmptyHash>>();

// 2. "hello" Message Verification
export type HashHello = SHA256<"hello">;
export type ExpectedHelloHash = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824";
staticAssert<Equal<HashHello, ExpectedHelloHash>>();
