import Base

namespace Tasks

def d09 : Prop :=
  ∀ (G H K : Type) (g : Foundation.Group G) (h : Foundation.Group H) (k : Foundation.Group K)
    (f : G → H) (q : G → K)
    (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (hq : ∀ x y, q (g.mul x y) = k.mul (q x) (q y))
    (x y : G), f x = h.one → f y = h.one → q x = k.one → q y = k.one →
    f (g.mul x y) = h.one ∧ q (g.mul x y) = k.one

end Tasks
