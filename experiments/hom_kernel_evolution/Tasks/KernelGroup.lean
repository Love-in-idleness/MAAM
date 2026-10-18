import Base
namespace Tasks
def kernelGroup : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (_hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y)),
    ∃ k : Foundation.Group {x : G // f x = h.one},
      k.one.val = g.one ∧
      (∀ x y, (k.mul x y).val = g.mul x.val y.val) ∧
      (∀ x, (k.inv x).val = g.inv x.val)
end Tasks
