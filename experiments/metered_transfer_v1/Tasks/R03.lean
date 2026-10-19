import Base

namespace Tasks

def r03 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (x y : G),
    f (g.mul (g.mul (g.mul x y) (g.inv x)) (g.inv y)) = h.one ↔
    h.mul (f x) (f y) = h.mul (f y) (f x)

end Tasks
