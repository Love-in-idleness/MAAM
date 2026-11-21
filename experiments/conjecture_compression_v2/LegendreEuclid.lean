import Assumption

open Bool Subtype

namespace Nat

theorem _root_.Bench.proof (h : Bench.A) (n : ℕ) : ∃ p, n ≤ p ∧ Prime p := by
  obtain ⟨p, lo, _, hp⟩ := h (n + 1) (Nat.succ_pos n)
  exact ⟨p, (Nat.le_succ n).trans ((Nat.le_mul_self _).trans lo.le), hp⟩

end Nat
