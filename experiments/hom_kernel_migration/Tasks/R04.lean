import Base

namespace Tasks

def r04 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (P Q : H → Prop)
    (hP : ∀ a b, P a → P b → P (h.mul a b))
    (hQ : ∀ a b, Q a → Q b → Q (h.mul a b))
    (x y : G), (P (f x) ∧ Q (f x)) → (P (f y) ∧ Q (f y)) →
    P (f (g.mul x y)) ∧ Q (f (g.mul x y))

end Tasks
