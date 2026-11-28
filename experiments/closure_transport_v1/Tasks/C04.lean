import Products

namespace ClosureTransport.Tasks

def c04 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f q : G → H)
    (_hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (_hq : ∀ x y, q (g.mul x y) = h.mul (q x) (q y)),
    ∃ F : Theory.Hom g (Foundation.prodGroup h h),
      (∀ x, F.toFun x = (f x, q x)) ∧
      ∀ x y,
        (F.toFun x).1 = (F.toFun x).2 →
        (F.toFun y).1 = (F.toFun y).2 →
        (F.toFun (g.mul x y)).1 = (F.toFun (g.mul x y)).2

end ClosureTransport.Tasks
