import Products

namespace ClosureTransport.Tasks

def c06 : Prop :=
  (∀ x y : Bool, (id : Bool → Bool) (Foundation.boolXorGroup.mul x y) =
    Foundation.boolXorGroup.mul (id x) (id y)) ∧
  ∃ x y : Bool, x = true ∧ y = true ∧
    Foundation.boolXorGroup.mul x y ≠ true

end ClosureTransport.Tasks
