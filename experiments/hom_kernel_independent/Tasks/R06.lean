import Base

namespace Tasks

def r06 : Prop :=
  ∀ (I G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → I → H) (hf : ∀ x y i, f (g.mul x y) i = h.mul (f x i) (f y i))
    (x y : G), f x = (fun _ => h.one) → f y = (fun _ => h.one) →
    f (g.mul x y) = (fun _ => h.one)

end Tasks
