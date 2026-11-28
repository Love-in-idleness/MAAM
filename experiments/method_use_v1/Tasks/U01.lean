import Base

namespace MethodUse.Tasks

def u01 : Prop :=
  ∀ (G : Type) (g : Foundation.Group G) (a x y : G),
    g.mul a x = g.mul a y → x = y

end MethodUse.Tasks
