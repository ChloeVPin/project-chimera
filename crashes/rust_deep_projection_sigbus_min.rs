#![recursion_limit = "10000000"]
pub struct S<T>(std::marker::PhantomData<T>);
pub trait Trait { type Out; }
impl Trait for () { type Out = (); }
impl<T: Trait> Trait for S<T> { type Out = S<<T as Trait>::Out>; }
type N1<T> = S<S<S<S<S<S<S<S<S<S<T>>>>>>>>>>;
type N2<T> = N1<N1<N1<N1<N1<N1<N1<N1<N1<N1<T>>>>>>>>>>;
type N3<T> = N2<N2<N2<N2<N2<N2<N2<N2<N2<N2<T>>>>>>>>>>;
type N4<T> = N3<N3<N3<N3<N3<N3<N3<N3<N3<N3<T>>>>>>>>>>;
pub type Trigger = <N4<N4<()>> as Trait>::Out;
