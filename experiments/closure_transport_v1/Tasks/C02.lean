import Products

namespace ClosureTransport.Tasks

def c02 : Prop :=
  ∀ (G H J : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (j : Foundation.Group J) (f : G → H) (q : H → J)
    (_hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (_hq : ∀ u v, q (h.mul u v) = j.mul (q u) (q v))
    (P : J → Prop) (_hP : ∀ u v, P u → P v → P (j.mul u v)),
    ∃ F : Theory.Hom g j,
      (∀ x, F.toFun x = q (f x)) ∧
      ∀ x y, P (F.toFun x) → P (F.toFun y) → P (F.toFun (g.mul x y))

end ClosureTransport.Tasks
