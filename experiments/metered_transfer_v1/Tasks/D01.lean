import Base

namespace Tasks

def d01 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (x y z : G), f (g.mul x y) = f z →
    f y = h.mul (h.inv (f x)) (f z)

end Tasks
