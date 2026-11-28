import Base
import Tasks.KernelGroup
import RefactorShared

namespace Submission
theorem solve_kernel_group : Tasks.kernelGroup :=
by
  intro G H g h f hf
  have hone := Refactored.shared_1 G H g h f hf
  have hinv := Refactored.shared_2 G H g h f hf hone
  let kone : {x : G // f x = h.one} := ⟨g.one, hone⟩
  let kmul : {x : G // f x = h.one} → {x : G // f x = h.one} →
      {x : G // f x = h.one} := fun x y =>
    ⟨g.mul x.val y.val, by rw [hf, x.property, y.property, h.one_mul]⟩
  let kinv : {x : G // f x = h.one} → {x : G // f x = h.one} :=
    fun x => ⟨g.inv x.val, hinv x.val x.property⟩
  let k : Foundation.Group {x : G // f x = h.one} := {
    one := kone
    mul := kmul
    inv := kinv
    one_mul := by
      intro x
      apply Subtype.ext
      exact g.one_mul x.val
    mul_one := by
      intro x
      apply Subtype.ext
      exact g.mul_one x.val
    mul_assoc := by
      intro x y z
      apply Subtype.ext
      exact g.mul_assoc x.val y.val z.val
    inv_mul := by
      intro x
      apply Subtype.ext
      exact g.inv_mul x.val
  }
  exact ⟨k, rfl, (by intro x y; rfl), (by intro x; rfl)⟩

end Submission
