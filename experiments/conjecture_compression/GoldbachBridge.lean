import Assumption

open Bool Subtype

namespace Nat

theorem _root_.Bench.proof (h : Bench.A) (n : ℕ) : ∃ p, n ≤ p ∧ Prime p := by
  obtain ⟨p, q, hp, hq, hsum⟩ := h (n + 2) (by omega)
  by_cases hn : n ≤ p
  · exact ⟨p, hn, hp⟩
  · exact ⟨q, by omega, hq⟩

end Nat
