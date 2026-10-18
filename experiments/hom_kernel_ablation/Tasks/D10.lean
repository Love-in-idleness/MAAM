import Base

namespace Tasks

def d10 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (x y z : G), z = g.mul x y → f x = h.one → f y = h.one → f z = h.one

end Tasks
