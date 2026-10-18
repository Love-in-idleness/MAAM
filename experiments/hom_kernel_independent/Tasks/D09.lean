import Base

namespace Tasks

def d09 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (a b : H), (∃ x, f x = a) → (∃ y, f y = b) → ∃ z, f z = h.mul a b

end Tasks
