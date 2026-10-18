import Base

namespace Baseline

theorem kernelMul : Foundation.kernelMulGoal := by
  intro G H g h f hf x y hx hy
  calc
    f (g.mul x y) = h.mul (f x) (f y) := hf x y
    _ = h.mul h.one (f y) := congrArg (fun z => h.mul z (f y)) hx
    _ = h.mul h.one h.one := congrArg (fun z => h.mul h.one z) hy
    _ = h.one := h.one_mul h.one

end Baseline
