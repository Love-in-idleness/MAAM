import Base

namespace Tasks

def r07 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (a x : G), f x = h.one → f (g.mul (g.mul a x) (g.inv a)) = h.one

end Tasks
