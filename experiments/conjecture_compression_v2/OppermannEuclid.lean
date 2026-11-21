import Assumption

open Bool Subtype

namespace Nat

theorem _root_.Bench.proof (h : Bench.A) (n : ℕ) : ∃ p, n ≤ p ∧ Prime p := by
  obtain ⟨p, lo, _, hp⟩ := (h (n + 2) (by omega)).2
  exact ⟨p, (show n ≤ n + 2 by omega).trans ((Nat.le_mul_self _).trans lo.le), hp⟩

end Nat
