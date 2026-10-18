import Base

namespace Tasks

def r05 : Prop :=
  ∀ (I G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : I → G → H) (hf : ∀ i x y, f i (g.mul x y) = h.mul (f i x) (f i y))
    (x y : G), (∀ i, f i x = h.one) → (∀ i, f i y = h.one) →
    ∀ i, f i (g.mul x y) = h.one

end Tasks
