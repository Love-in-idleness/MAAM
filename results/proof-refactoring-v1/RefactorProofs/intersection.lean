import Base
import Tasks.Intersection
import RefactorShared

namespace Submission
theorem solve_intersection : Tasks.intersection :=
by
  intro G H J g h j f q hf hq
  have hom_one : ∀ {A B : Type} (a : Foundation.Group A) (b : Foundation.Group B) (r : A → B),
      (∀ (x y : A), r (a.mul x y) = b.mul (r x) (r y)) → r a.one = b.one := by exact?
  have inv_closed : ∀ {A B : Type} (a : Foundation.Group A)
      (b : Foundation.Group B) (r : A → B)
      (hr : ∀ x y, r (a.mul x y) = b.mul (r x) (r y))
      (x : A), r x = b.one → r (a.inv x) = b.one := by
    intro A B a b r hr x hx
    calc
      r (a.inv x) = b.mul (r (a.inv x)) b.one := (b.mul_one _).symm
      _ = b.mul (r (a.inv x)) (r x) := by rw [hx]
      _ = r (a.mul (a.inv x) x) := (hr _ _).symm
      _ = r a.one := by rw [a.inv_mul]
      _ = b.one := hom_one a b r hr
  let K := {x : G // f x = h.one ∧ q x = j.one}
  let e : K := ⟨g.one, hom_one g h f hf, hom_one g j q hq⟩
  let m : K → K → K := fun x y => ⟨g.mul x.val y.val,
    by rw [hf, x.property.1, y.property.1, h.one_mul],
    by rw [hq, x.property.2, y.property.2, j.one_mul]⟩
  let i : K → K := fun x => ⟨g.inv x.val,
    inv_closed g h f hf x.val x.property.1,
    inv_closed g j q hq x.val x.property.2⟩
  have left_id : ∀ x : K, m e x = x := by
    intro x
    apply Subtype.eq
    exact g.one_mul x.val
  have right_id : ∀ x : K, m x e = x := by
    intro x
    apply Subtype.eq
    exact g.mul_one x.val
  have assoc : ∀ x y z : K, m (m x y) z = m x (m y z) := by
    intro x y z
    apply Subtype.eq
    exact g.mul_assoc x.val y.val z.val
  have left_inv : ∀ x : K, m (i x) x = e := by
    intro x
    apply Subtype.eq
    exact g.inv_mul x.val
  let k : Foundation.Group K := {
    one := e
    mul := m
    inv := i
    one_mul := left_id
    mul_one := right_id
    mul_assoc := assoc
    inv_mul := left_inv
  }
  exact ⟨k, rfl, (fun _ _ => rfl), (fun _ => rfl)⟩

end Submission
