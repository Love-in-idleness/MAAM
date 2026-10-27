import Base

namespace MethodUse.Tasks

def u02 : Prop :=
  ∀ (G : Type) (g : Foundation.Group G) (a x c : G),
    c = g.mul a x → x = g.mul (g.inv a) c

end MethodUse.Tasks
