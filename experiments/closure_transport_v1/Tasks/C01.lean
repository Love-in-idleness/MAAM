import Products

namespace ClosureTransport.Tasks

def c01 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (P : H → Prop) (_hP : ∀ u v, P u → P v → P (h.mul u v)),
    ∃ F : Theory.Hom g h,
      (∀ x, F.toFun x = f x) ∧
      ∀ x y, P (F.toFun x) → P (F.toFun y) → P (F.toFun (g.mul x y))

end ClosureTransport.Tasks
