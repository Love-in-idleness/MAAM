import Base
namespace Tasks
def restriction : Prop :=
  ∀ (A G H : Type) (a : Foundation.Group A) (g : Foundation.Group G)
    (h : Foundation.Group H) (f : G → H)
    (_hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (u : A → G) (_hu : ∀ x y, u (a.mul x y) = g.mul (u x) (u y))
    (_image : ∀ x, f (u x) = h.one),
    ∃ (k : Foundation.Group {x : G // f x = h.one})
      (v : A → {x : G // f x = h.one}),
      (∀ x, (v x).val = u x) ∧
      (∀ x y, v (a.mul x y) = k.mul (v x) (v y)) ∧
      k.one.val = g.one ∧
      (∀ x y, (k.mul x y).val = g.mul x.val y.val) ∧
      (∀ x, (k.inv x).val = g.inv x.val)
end Tasks
