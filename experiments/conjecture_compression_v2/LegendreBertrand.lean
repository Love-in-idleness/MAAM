import Assumption

namespace Nat

theorem _root_.Bench.proof (h : Bench.A) (n : ℕ) (n_large : 512 ≤ n) :
    ∃ p : ℕ, p.Prime ∧ n < p ∧ p ≤ 2 * n := by
  let k := n.sqrt
  have hk : 5 ≤ k := Nat.le_sqrt.2 (by omega)
  obtain ⟨p, lo, hi, prime⟩ := h (k + 1) (by omega)
  refine ⟨p, prime, (Nat.lt_succ_sqrt n).trans lo, hi.le.trans ?_⟩
  have hs : k * k ≤ n := Nat.sqrt_le n
  nlinarith [Nat.mul_le_mul_right k hk]

end Nat
