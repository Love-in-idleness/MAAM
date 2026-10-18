import Base

namespace Tasks

def d01 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (a b c d : G), f a = h.one → f b = h.one → f c = h.one → f d = h.one →
    f (g.mul (g.mul a b) (g.mul c d)) = h.one

end Tasks
