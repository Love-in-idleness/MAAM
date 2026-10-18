import Base

namespace Tasks

def r07 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (z : G), f z = h.one → ∀ (xs : List {x : G // f x = h.one}),
    f (List.foldl (fun acc a => g.mul acc a.val) z xs) = h.one

end Tasks
