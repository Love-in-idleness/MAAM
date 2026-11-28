/- Isolated foundation: no Mathlib and no pre-existing homomorphism API. -/
namespace Foundation

structure Group (G : Type) where
  one : G
  mul : G → G → G
  inv : G → G
  one_mul : ∀ x, mul one x = x
  mul_one : ∀ x, mul x one = x
  mul_assoc : ∀ x y z, mul (mul x y) z = mul x (mul y z)
  inv_mul : ∀ x, mul (inv x) x = one

def kernelMulGoal : Prop :=
  ∀ (G H : Type) (g : Group G) (h : Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (x y : G), f x = h.one → f y = h.one → f (g.mul x y) = h.one

end Foundation
