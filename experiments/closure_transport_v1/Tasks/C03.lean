import Products

namespace ClosureTransport.Tasks

def c03 : Prop :=
  ∀ (G H J : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (j : Foundation.Group J) (f : G → H) (q : G → J)
    (_hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (_hq : ∀ x y, q (g.mul x y) = j.mul (q x) (q y))
    (P : H → Prop) (Q : J → Prop)
    (_hP : ∀ u v, P u → P v → P (h.mul u v))
    (_hQ : ∀ u v, Q u → Q v → Q (j.mul u v)),
    ∃ F : Theory.Hom g (Foundation.prodGroup h j),
      (∀ x, F.toFun x = (f x, q x)) ∧
      ∀ x y,
        (P (F.toFun x).1 ∧ Q (F.toFun x).2) →
        (P (F.toFun y).1 ∧ Q (F.toFun y).2) →
        P (F.toFun (g.mul x y)).1 ∧ Q (F.toFun (g.mul x y)).2

end ClosureTransport.Tasks
