import Base

namespace Tasks

def d07 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (x y z : G), f x = h.one → f y = f z → f (g.mul x y) = f z

end Tasks
