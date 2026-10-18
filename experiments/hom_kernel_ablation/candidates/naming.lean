import Base

namespace Theory

abbrev Multiplicative {G H : Type} (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) : Prop := ∀ x y, f (g.mul x y) = h.mul (f x) (f y)

abbrev Fibre {G H : Type} (h : Foundation.Group H) (f : G → H) (x : G) : Prop :=
  f x = h.one

end Theory
