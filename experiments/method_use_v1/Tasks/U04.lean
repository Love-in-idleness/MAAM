import Base

namespace MethodUse.Tasks

def u04 : Prop :=
  ∀ (X H : Type) (h : Foundation.Group H) (f : X → H)
    (hf : ∀ x y, f x = f y → x = y) (a : H) (x y : X),
    h.mul a (f x) = h.mul a (f y) → x = y

end MethodUse.Tasks
