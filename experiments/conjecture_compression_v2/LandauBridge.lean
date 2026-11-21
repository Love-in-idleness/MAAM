import Assumption

open Bool Subtype

namespace Nat

theorem _root_.Bench.proof (h : Bench.A) (n : ℕ) : ∃ p, n ≤ p ∧ Prime p := by
  obtain ⟨k, lo, prime⟩ := h n
  exact ⟨_, lo.trans ((Nat.le_mul_self k).trans (Nat.le_succ _)), prime⟩

end Nat
