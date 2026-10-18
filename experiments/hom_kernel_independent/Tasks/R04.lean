import Base

namespace Tasks

def r04 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (xs : List G) (z : G),
    f (List.foldl g.mul z xs) = List.foldl h.mul (f z) (List.map f xs)

end Tasks
