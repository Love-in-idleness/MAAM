import Base

namespace Tasks

def d03 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (x : G), g.mul x x = g.one → h.mul (f x) (f x) = h.one

end Tasks
