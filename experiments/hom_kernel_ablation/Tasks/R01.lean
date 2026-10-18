import Base

namespace Tasks

def r01 : Prop :=
  ∀ (G H K : Type) (g : Foundation.Group G) (h : Foundation.Group H) (k : Foundation.Group K)
    (f : G → H) (q : H → K)
    (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (hq : ∀ x y, q (h.mul x y) = k.mul (q x) (q y))
    (x y : G), q (f x) = k.one → q (f y) = k.one → q (f (g.mul x y)) = k.one

end Tasks
