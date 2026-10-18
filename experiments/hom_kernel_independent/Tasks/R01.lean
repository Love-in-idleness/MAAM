import Base

namespace Tasks

def r01 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (x x' y y' : G), f x = f x' → f y = f y' →
    f (g.mul x y) = f (g.mul x' y')

end Tasks
