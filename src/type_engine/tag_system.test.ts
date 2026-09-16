/**
 * Project Chimera: Verification Suite for Post 2-Tag Engine
 */

import { Equal, staticAssert } from './assertions';
import { CollatzTagRules, Run2Tag, Step2Tag } from './tag_system';

// Test Vector 1: Single Step Evolution
type Word0 = ['a', 'b', 'c', 'a'];
// S1 = 'a', S2 = 'b', Rest = ['c', 'a'], R('a') = ['b', 'c']
// Next = ['c', 'a', 'b', 'c']
type Step1 = Step2Tag<Word0, CollatzTagRules>;
staticAssert<Equal<Step1, ['c', 'a', 'b', 'c']>>();

// Step 2:
// S1 = 'c', S2 = 'a', Rest = ['b', 'c'], R('c') = ['a', 'a', 'a']
// Next = ['b', 'c', 'a', 'a', 'a']
type Step2 = Step2Tag<Step1, CollatzTagRules>;
staticAssert<Equal<Step2, ['b', 'c', 'a', 'a', 'a']>>();

// Step 3:
// S1 = 'b', S2 = 'c', Rest = ['a', 'a', 'a'], R('b') = ['a']
// Next = ['a', 'a', 'a', 'a']
type Step3 = Step2Tag<Step2, CollatzTagRules>;
staticAssert<Equal<Step3, ['a', 'a', 'a', 'a']>>();

// Multi-step Run2Tag
type Run3 = Run2Tag<Word0, CollatzTagRules, 3>;
staticAssert<Equal<Run3, ['a', 'a', 'a', 'a']>>();

// Halting verification: ['a'] halts because length < 2
type HaltingWord = ['a'];
type HaltedStep = Step2Tag<HaltingWord, CollatzTagRules>;
staticAssert<Equal<HaltedStep, []>>();
