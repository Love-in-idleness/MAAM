import Base

namespace Tasks

def d02 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (op : G → G → G) (hop : ∀ x y, op x y = g.mul y x)
    (x y z : G), f x = h.one → f y = h.one → f z = h.one →
    f (op (op x y) z) = h.one

end Tasks
