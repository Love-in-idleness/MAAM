import Products

namespace Theory

def MulClosed {G : Type} (g : Foundation.Group G) (P : G → Prop) : Prop :=
  ∀ x y, P x → P y → P (g.mul x y)

theorem preimage_mul_closed {G H : Type} {g : Foundation.Group G}
    {h : Foundation.Group H} (F : Hom g h) (P : H → Prop)
    (hP : MulClosed h P) : MulClosed g (fun x => P (F.toFun x)) := by
  intro x y hx hy
  rw [F.map_mul x y]
  exact hP (F.toFun x) (F.toFun y) hx hy

end Theory
