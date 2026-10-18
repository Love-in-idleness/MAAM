import Base

namespace Tasks

def d11 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (x : G), f x = h.one → ∀ n : Nat,
    f (Nat.rec x (fun _ acc => g.mul acc acc) n) = h.one

end Tasks
