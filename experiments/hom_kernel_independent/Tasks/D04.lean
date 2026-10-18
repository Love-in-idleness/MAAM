import Base

namespace Tasks

def d04 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (x y z : G), f x = f y → (f (g.mul x z) = h.one ↔ f (g.mul y z) = h.one)

end Tasks
