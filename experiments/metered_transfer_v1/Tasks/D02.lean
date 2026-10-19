import Base

namespace Tasks

def d02 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (x y z : G), f (g.mul y x) = f z →
    f y = h.mul (f z) (h.inv (f x))

end Tasks
