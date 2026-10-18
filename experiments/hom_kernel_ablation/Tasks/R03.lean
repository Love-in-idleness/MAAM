import Base

namespace Tasks

def r03 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (P : H → Prop) (hP : ∀ a b, P a → P b → P (h.mul a b))
    (x y : G), P (f x) → P (f y) → P (f (g.mul x y))

end Tasks
