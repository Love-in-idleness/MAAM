import Base
namespace Tasks
inductive Word (G : Type) where
  | unit : Word G
  | atom : G → Word G
  | product : Word G → Word G → Word G
  | inverse : Word G → Word G

def Word.eval {G : Type} (g : Foundation.Group G) : Word G → G
  | .unit => g.one
  | .atom x => x
  | .product x y => g.mul (x.eval g) (y.eval g)
  | .inverse x => g.inv (x.eval g)

def Word.admissible {G : Type} (p : G → Prop) : Word G → Prop
  | .unit => True
  | .atom x => p x
  | .product x y => x.admissible p ∧ y.admissible p
  | .inverse x => x.admissible p

def words : Prop :=
  ∀ (G H : Type) (g : Foundation.Group G) (h : Foundation.Group H)
    (f : G → H) (_hf : ∀ x y, f (g.mul x y) = h.mul (f x) (f y))
    (w : Word G), w.admissible (fun x => f x = h.one) → f (w.eval g) = h.one
end Tasks
