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

theorem kernel_mul {G H : Type} {g : Foundation.Group G} {h : Foundation.Group H}
    (f : Hom g h) {x y : G} (hx : kernel f x) (hy : kernel f y) :
    kernel f (g.mul x y) := by
  change f.toFun (g.mul x y) = h.one
  calc
    f.toFun (g.mul x y) = h.mul (f.toFun x) (f.toFun y) := f.map_mul x y
    _ = h.mul h.one (f.toFun y) := congrArg (fun z => h.mul z (f.toFun y)) hx
    _ = h.mul h.one h.one := congrArg (fun z => h.mul h.one z) hy
    _ = h.one := h.one_mul h.one

def Kernel.mul {G H : Type} {g : Foundation.Group G} {h : Foundation.Group H}
    {f : Hom g h} (x y : Kernel f) : Kernel f :=
  ⟨g.mul x.val y.val, kernel_mul f x.property y.property⟩

end Theory
