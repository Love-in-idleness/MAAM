import Base
namespace Tasks
def intersection : Prop :=
  ∀ (G H J : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (j : Foundation.Group J) (f : G → H) (q : G → J)
    (_hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (_hq : ∀ x y, q (g.mul x y) = j.mul (q x) (q y)),
    ∃ k : Foundation.Group {x : G // f x = h.one ∧ q x = j.one},
      k.one.val = g.one ∧
      (∀ x y, (k.mul x y).val = g.mul x.val y.val) ∧
      (∀ x, (k.inv x).val = g.inv x.val)
end Tasks
