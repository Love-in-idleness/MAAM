import Base

namespace Tasks

def d10 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (s : H → G) (hs : ∀ a, f (s a) = a)
    (x y : H), ∃ z : G, f z = h.mul x y ∧ z = g.mul (s x) (s y)

end Tasks
