import Base

namespace Theory

structure Hom {G H : Type} (g : Foundation.Group G) (h : Foundation.Group H) where
  toFun : G → H
  map_mul : ∀ x y, toFun (g.mul x y) = h.mul (toFun x) (toFun y)

def kernel {G H : Type} {g : Foundation.Group G} {h : Foundation.Group H}
    (f : Hom g h) (x : G) : Prop :=
  f.toFun x = h.one

def Kernel {G H : Type} {g : Foundation.Group G} {h : Foundation.Group H}
    (f : Hom g h) : Type :=
  { x : G // kernel f x }

end Theory
