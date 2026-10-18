import Base

namespace Tasks

inductive Tree (A : Type) where
  | leaf : A → Tree A
  | branch : Tree A → Tree A → Tree A

def Tree.eval {A G : Type} (g : Foundation.Group G) (v : A → G) : Tree A → G
  | .leaf x => v x
  | .branch l r => g.mul (Tree.eval g v l) (Tree.eval g v r)

def r03 : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (t : Tasks.Tree {x : G // f x = h.one}),
    f (Tasks.Tree.eval g (fun x => x.val) t) = h.one

end Tasks
