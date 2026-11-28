import Base

namespace Refactored

theorem shared_1
    (G : Type)
    (H : Type)
    (g : Foundation.Group G)
    (h : Foundation.Group H)
    (f : G → H)
    (hf : ∀ (x y : G), f (g.mul x y) = h.mul (f x) (f y)) : f g.one = h.one := by
  have hid : f g.one = h.mul (f g.one) (f g.one) := by
    simpa only [g.one_mul] using hf g.one g.one
  calc
    f g.one = h.mul h.one (f g.one) := (h.one_mul _).symm
    _ = h.mul (h.mul (h.inv (f g.one)) (f g.one)) (f g.one) := by
      rw [h.inv_mul]
    _ = h.mul (h.inv (f g.one)) (h.mul (f g.one) (f g.one)) :=
      h.mul_assoc _ _ _
    _ = h.mul (h.inv (f g.one)) (f g.one) :=
      congrArg (h.mul (h.inv (f g.one))) hid.symm
    _ = h.one := h.inv_mul _

theorem shared_2
    (G : Type)
    (H : Type)
    (g : Foundation.Group G)
    (h : Foundation.Group H)
    (f : G → H)
    (hf : ∀ (x y : G), f (g.mul x y) = h.mul (f x) (f y))
    (hone : f g.one = h.one) : ∀ (x : G), f x = h.one → f (g.inv x) = h.one := fun x hx =>
    trans
      (trans
        (trans (trans (Eq.symm (h.mul_one (f (g.inv x)))) (congrArg (h.mul (f (g.inv x))) (Eq.symm hx)))
          (Eq.symm (hf (g.inv x) x)))
        (congrArg f (g.inv_mul x)))
      hone

end Refactored
