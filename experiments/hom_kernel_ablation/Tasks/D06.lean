import Base

namespace Tasks

def d06 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (x y : G), f y = h.one → f (g.mul x y) = f x

end Tasks
