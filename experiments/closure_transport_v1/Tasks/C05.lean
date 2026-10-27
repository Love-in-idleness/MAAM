import Products

namespace ClosureTransport.Tasks

def c05 : Prop :=
  (∀ u v : Bool, u = false → v = false →
    Foundation.boolXorGroup.mul u v = false) ∧
  (∃ x y : Bool, Bool.not x = false ∧ Bool.not y = false ∧
    Bool.not (Foundation.boolXorGroup.mul x y) ≠ false) ∧
  ¬ (∀ x y : Bool, Bool.not (Foundation.boolXorGroup.mul x y) =
    Foundation.boolXorGroup.mul (Bool.not x) (Bool.not y))

end ClosureTransport.Tasks
