import Base

namespace Tasks

def r01 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (s : H → G) (hs : ∀ y, f (s y) = y) (x : G),
    ∃ k : {z : G // f z = h.one}, g.mul k.val (s (f x)) = x

end Tasks
