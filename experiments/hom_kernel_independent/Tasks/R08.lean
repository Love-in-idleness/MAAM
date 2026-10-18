import Base

namespace Tasks

def r08 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (a x y : G), f x = f y →
    f (g.mul (g.mul a x) (g.inv a)) = f (g.mul (g.mul a y) (g.inv a))

end Tasks
