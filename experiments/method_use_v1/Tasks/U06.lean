import Base

namespace MethodUse.Tasks

def u06 : Prop :=
  ∀ (X Y : Type) (f : X → Y) (x y : X), x = y → f x = f y

end MethodUse.Tasks
