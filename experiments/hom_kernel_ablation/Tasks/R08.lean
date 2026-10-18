import Base

namespace Tasks

def r08 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (x z : G), f x = h.one → f z = h.one → ∀ (n : Nat),
    f (Nat.rec z (fun _ acc => g.mul acc x) n) = h.one

end Tasks
