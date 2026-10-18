import Base

namespace Tasks

def d03 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (x y z : G), f x = h.one → f y = h.one → f z = h.one →
    f (g.mul (g.mul x y) z) = h.one

end Tasks
