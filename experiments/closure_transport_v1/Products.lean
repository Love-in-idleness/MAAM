import Candidate

namespace Foundation

def prodGroup {G H : Type} (g : Group G) (h : Group H) : Group (G × H) where
  one := (g.one, h.one)
  mul := fun x y => (g.mul x.1 y.1, h.mul x.2 y.2)
  inv := fun x => (g.inv x.1, h.inv x.2)
  one_mul := fun x => Prod.ext (g.one_mul x.1) (h.one_mul x.2)
  mul_one := fun x => Prod.ext (g.mul_one x.1) (h.mul_one x.2)
  mul_assoc := fun x y z => Prod.ext (g.mul_assoc x.1 y.1 z.1) (h.mul_assoc x.2 y.2 z.2)
  inv_mul := fun x => Prod.ext (g.inv_mul x.1) (h.inv_mul x.2)

def boolXorGroup : Group Bool where
  one := false
  mul := Bool.xor
  inv := id
  one_mul := by decide
  mul_one := by decide
  mul_assoc := by decide
  inv_mul := by decide

end Foundation
