import Base
import Tasks.Restriction
import RefactorShared

namespace Submission
theorem solve_restriction : Tasks.restriction :=
by
  intro A G H a g h f hf u hu himage
  have hone := Refactored.shared_1 G H g h f hf
  have hmul : ∀ (x y : { x // f x = h.one }), f (g.mul x.val y.val) = h.one := fun x y =>
      trans
        (trans (trans (hf x.val y.val) (congrArg (fun z => h.mul z (f y.val)) x.property))
          (congrArg (h.mul h.one) y.property))
        (h.one_mul h.one)
  have hinv : ∀ (x : { x // f x = h.one }), f (g.inv x.val) = h.one := fun x =>
      trans
        (trans
          (trans
            (trans (Eq.symm (h.mul_one (f (g.inv x.val))))
              (congrArg (fun z => h.mul (f (g.inv x.val)) z) (Eq.symm x.property)))
            (Eq.symm (hf (g.inv x.val) x.val)))
          (congrArg f (g.inv_mul x.val)))
        hone
  let k : Foundation.Group {x : G // f x = h.one} := {
    one := ⟨g.one, hone⟩
    mul := fun x y => ⟨g.mul x.val y.val, hmul x y⟩
    inv := fun x => ⟨g.inv x.val, hinv x⟩
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
  let v : A → {x : G // f x = h.one} := fun x => ⟨u x, himage x⟩
  refine ⟨k, v, ?_, ?_, ?_, ?_, ?_⟩
  · intro x
    rfl
  · intro x y
    apply Subtype.ext
    exact hu x y
  · rfl
  · intro x y
    rfl
  · intro x
    rfl

end Submission
