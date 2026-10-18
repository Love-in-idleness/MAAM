import Candidate

namespace Treatment

theorem kernelMul : Foundation.kernelMulGoal := by
  intro G H g h f hf x y hx hy
  let F : Theory.Hom g h := ⟨f, hf⟩
  exact Theory.kernel_mul F hx hy

end Treatment
