import Assumption

open Bool Subtype

namespace Nat

theorem _root_.Bench.proof (h : Bench.A) (n : ℕ) : ∃ p, n ≤ p ∧ Prime p := by
  obtain ⟨p, lo, prime, _⟩ := h n
  exact ⟨p, lo, prime⟩

end Nat
