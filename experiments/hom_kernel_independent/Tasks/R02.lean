import Base

namespace Tasks

def r02 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (x y : G), f (g.mul (g.inv x) y) = h.one ↔ f x = f y

end Tasks
