import Base

namespace Tasks

def r02 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (s : H → G) (hs : ∀ y, f (s y) = y)
    (k l : {z : G // f z = h.one}) (a b : H),
    g.mul k.val (s a) = g.mul l.val (s b) → k = l ∧ a = b

end Tasks
