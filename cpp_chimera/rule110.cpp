#include "rule110.hpp"

using namespace chimera;

// Test Vector 1: Initial Tape = [0, 1, 1, 0, 1, 1, 1, 0]
using InitialTape = Tape<0, 1, 1, 0, 1, 1, 1, 0>;
using ExpectedStep1 = Tape<1, 1, 1, 1, 1, 0, 1, 0>;
using ExpectedStep2 = Tape<1, 0, 0, 0, 1, 1, 1, 0>;
using ExpectedStep5 = Tape<1, 1, 1, 0, 0, 0, 1, 0>;

// Single step verification
using ActualStep1 = StepTape_t<InitialTape>;
static_assert(tape_equal_v<ActualStep1, ExpectedStep1>, "Step 1 must match");

using ActualStep2 = StepTape_t<ActualStep1>;
static_assert(tape_equal_v<ActualStep2, ExpectedStep2>, "Step 2 must match");

// Multi-step evolution verification
using ActualEvolved2 = Evolve_t<InitialTape, 2>;
static_assert(tape_equal_v<ActualEvolved2, ExpectedStep2>, "Evolve 2 must match");

using ActualEvolved5 = Evolve_t<InitialTape, 5>;
static_assert(tape_equal_v<ActualEvolved5, ExpectedStep5>, "Evolve 5 must match");

// Baseline 100-step evolution check
using Evolved100 = Evolve_t<InitialTape, 100>;

int main() {
    return 0;
}
