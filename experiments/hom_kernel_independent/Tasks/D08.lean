import Base

namespace Tasks

def d08 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (op : {x : G // f x = h.one} → {x : G // f x = h.one} → {x : G // f x = h.one})
    (hop : ∀ x y, (op x y).val = g.mul x.val y.val),
    ∀ x y z, op (op x y) z = op x (op y z)

end Tasks
