/- Genuine small Lean propositions for the optional exporter smoke check. -/
namespace Demo

theorem andRight (A B : Prop) : A ∧ B → B := fun h => And.right h

theorem modusPonens (A B : Prop) : (A → B) → A → B := fun h a => h a

theorem andSwap (A B : Prop) : A ∧ B → B ∧ A :=
  fun h => ⟨h.right, h.left⟩

theorem admittedExample : False := by sorry

end Demo
