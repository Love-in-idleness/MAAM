import Base

namespace Tasks

def d12 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (x y : G), f x = h.one → f y = h.one → ∀ n : Nat,
    let p : G × G := Nat.rec (x, y) (fun _ p => (g.mul p.1 p.2, g.mul p.2 p.1)) n
    f p.1 = h.one ∧ f p.2 = h.one

end Tasks
