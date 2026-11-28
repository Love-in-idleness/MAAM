import Base

namespace MethodUse.Tasks

def u03 : Prop :=
  ∀ (G : Type) (g : Foundation.Group G) (a b x y : G),
    g.mul a (g.mul b x) = g.mul a (g.mul b y) → x = y

end MethodUse.Tasks
