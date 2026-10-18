import Base

namespace Tasks

def r06 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f q : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (hq : ∀ x y, q (g.mul x y) = h.mul (q x) (q y))
    (x y z : G), f x = q x → f y = q y → f z = q z →
    f (g.mul (g.mul x y) z) = q (g.mul (g.mul x y) z)

end Tasks
