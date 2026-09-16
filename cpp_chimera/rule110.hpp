#pragma once

#include <type_traits>

namespace chimera {

// Elementary Rule 110 cell transition lookup
template<int L, int C, int R>
struct Rule110Transition;

template<> struct Rule110Transition<1, 1, 1> { static constexpr int value = 0; };
template<> struct Rule110Transition<1, 1, 0> { static constexpr int value = 1; };
template<> struct Rule110Transition<1, 0, 1> { static constexpr int value = 1; };
template<> struct Rule110Transition<1, 0, 0> { static constexpr int value = 0; };
template<> struct Rule110Transition<0, 1, 1> { static constexpr int value = 1; };
template<> struct Rule110Transition<0, 1, 0> { static constexpr int value = 1; };
template<> struct Rule110Transition<0, 0, 1> { static constexpr int value = 1; };
template<> struct Rule110Transition<0, 0, 0> { static constexpr int value = 0; };

template<int L, int C, int R>
inline constexpr int rule110_v = Rule110Transition<L, C, R>::value;

// Type-level tape container
template<int... Bits>
struct Tape {};

// StepTape helper: traverse tape with Dirichlet quiescent boundaries (0 on left, 0 on right)
template<typename InTape, typename OutTape, int Prev, int Curr>
struct StepWorker;

// Base case: tape exhausted; evaluate right boundary with 0
template<int... OutBits, int Prev, int Curr>
struct StepWorker<Tape<>, Tape<OutBits...>, Prev, Curr> {
    using type = Tape<OutBits..., rule110_v<Prev, Curr, 0>>;
};

// Inductive case: evaluate cell at Curr with neighbor Next
template<int Next, int... Rest, int... OutBits, int Prev, int Curr>
struct StepWorker<Tape<Next, Rest...>, Tape<OutBits...>, Prev, Curr> {
    using type = typename StepWorker<
        Tape<Rest...>,
        Tape<OutBits..., rule110_v<Prev, Curr, Next>>,
        Curr,
        Next
    >::type;
};

// Entry point for StepTape
template<typename T>
struct StepTape;

template<>
struct StepTape<Tape<>> {
    using type = Tape<>;
};

template<int B0>
struct StepTape<Tape<B0>> {
    using type = Tape<rule110_v<0, B0, 0>>;
};

template<int B0, int B1, int... Rest>
struct StepTape<Tape<B0, B1, Rest...>> {
    using type = typename StepWorker<
        Tape<Rest...>,
        Tape<rule110_v<0, B0, B1>>,
        B0,
        B1
    >::type;
};

template<typename T>
using StepTape_t = typename StepTape<T>::type;

// Recursive evolution
template<typename CurrentTape, int Steps>
struct Evolve {
    using type = typename Evolve<typename StepTape<CurrentTape>::type, Steps - 1>::type;
};

template<typename CurrentTape>
struct Evolve<CurrentTape, 0> {
    using type = CurrentTape;
};

template<typename CurrentTape, int Steps>
using Evolve_t = typename Evolve<CurrentTape, Steps>::type;

// Tape equality helper
template<typename T1, typename T2>
struct TapeEqual : std::false_type {};

template<int... Bits>
struct TapeEqual<Tape<Bits...>, Tape<Bits...>> : std::true_type {};

template<typename T1, typename T2>
inline constexpr bool tape_equal_v = TapeEqual<T1, T2>::value;

} // namespace chimera
