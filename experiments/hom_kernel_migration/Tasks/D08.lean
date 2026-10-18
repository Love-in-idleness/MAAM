import Base

namespace Tasks

def d08 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (x a y b : G), x = a → y = b → f x = h.one → f y = h.one → f (g.mul a b) = h.one

end Tasks
