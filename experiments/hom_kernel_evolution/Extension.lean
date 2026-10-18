import Candidate

/- A proved extension of the unchanged v1 package, over the same left-inverse
   foundation. Every helper below is part of the charged v2 package. -/
namespace Theory

namespace GroupFacts

theorem left_cancel {G : Type} (g : Foundation.Group G) (a b c : G)
    (e : g.mul a b = g.mul a c) : b = c := by
  calc
    b = g.mul g.one b := (g.one_mul b).symm
    _ = g.mul (g.mul (g.inv a) a) b :=
      congrArg (fun z => g.mul z b) (g.inv_mul a).symm
    _ = g.mul (g.inv a) (g.mul a b) := g.mul_assoc (g.inv a) a b
    _ = g.mul (g.inv a) (g.mul a c) := congrArg (g.mul (g.inv a)) e
    _ = g.mul (g.mul (g.inv a) a) c := (g.mul_assoc (g.inv a) a c).symm
    _ = g.mul g.one c := congrArg (fun z => g.mul z c) (g.inv_mul a)
    _ = c := g.one_mul c

theorem mul_inv {G : Type} (g : Foundation.Group G) (x : G) :
    g.mul x (g.inv x) = g.one := by
  apply left_cancel g (g.inv x)
  calc
    g.mul (g.inv x) (g.mul x (g.inv x)) =
        g.mul (g.mul (g.inv x) x) (g.inv x) :=
      (g.mul_assoc (g.inv x) x (g.inv x)).symm
    _ = g.mul g.one (g.inv x) := congrArg (fun z => g.mul z (g.inv x)) (g.inv_mul x)
    _ = g.inv x := g.one_mul (g.inv x)
    _ = g.mul (g.inv x) g.one := (g.mul_one (g.inv x)).symm

theorem inv_one {G : Type} (g : Foundation.Group G) : g.inv g.one = g.one :=
  (g.mul_one (g.inv g.one)).symm.trans (g.inv_mul g.one)

end GroupFacts

theorem Hom.map_one {G H : Type} {g : Foundation.Group G} {h : Foundation.Group H}
    (f : Hom g h) : f.toFun g.one = h.one := by
  apply GroupFacts.left_cancel h (f.toFun g.one)
  calc
    h.mul (f.toFun g.one) (f.toFun g.one) = f.toFun (g.mul g.one g.one) :=
      (f.map_mul g.one g.one).symm
    _ = f.toFun g.one := congrArg f.toFun (g.one_mul g.one)
    _ = h.mul (f.toFun g.one) h.one := (h.mul_one (f.toFun g.one)).symm

theorem Hom.map_inv {G H : Type} {g : Foundation.Group G} {h : Foundation.Group H}
    (f : Hom g h) (x : G) : f.toFun (g.inv x) = h.inv (f.toFun x) := by
  apply GroupFacts.left_cancel h (f.toFun x)
  calc
    h.mul (f.toFun x) (f.toFun (g.inv x)) = f.toFun (g.mul x (g.inv x)) :=
      (f.map_mul x (g.inv x)).symm
    _ = f.toFun g.one := congrArg f.toFun (GroupFacts.mul_inv g x)
    _ = h.one := f.map_one
    _ = h.mul (f.toFun x) (h.inv (f.toFun x)) :=
      (GroupFacts.mul_inv h (f.toFun x)).symm

theorem kernel_one {G H : Type} {g : Foundation.Group G} {h : Foundation.Group H}
    (f : Hom g h) : kernel f g.one := f.map_one

theorem kernel_inv {G H : Type} {g : Foundation.Group G} {h : Foundation.Group H}
    (f : Hom g h) {x : G} (hx : kernel f x) : kernel f (g.inv x) := by
  change f.toFun (g.inv x) = h.one
  calc
    f.toFun (g.inv x) = h.inv (f.toFun x) := f.map_inv x
    _ = h.inv h.one := congrArg h.inv hx
    _ = h.one := GroupFacts.inv_one h

def Kernel.group {G H : Type} {g : Foundation.Group G} {h : Foundation.Group H}
    (f : Hom g h) : Foundation.Group (Kernel f) where
  one := ⟨g.one, kernel_one f⟩
  mul := Kernel.mul
  inv := fun x => ⟨g.inv x.val, kernel_inv f x.property⟩
  one_mul := fun x => Subtype.eq (g.one_mul x.val)
  mul_one := fun x => Subtype.eq (g.mul_one x.val)
  mul_assoc := fun x y z => Subtype.eq (g.mul_assoc x.val y.val z.val)
  inv_mul := fun x => Subtype.eq (g.inv_mul x.val)

end Theory
