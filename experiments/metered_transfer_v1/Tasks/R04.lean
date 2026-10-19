import Base

namespace Tasks

def r04 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (surj : ∀ y : H, ∃ x : G, f x = y),
    (∀ x y : G, f (g.mul (g.mul (g.mul x y) (g.inv x)) (g.inv y)) = h.one) ↔
    (∀ a b : H, h.mul a b = h.mul b a)

end Tasks
