import Base

namespace Tasks

def d04 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (x : G), f x = h.inv (f x) ↔ f (g.mul x x) = h.one

end Tasks
