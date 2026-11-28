import Goal

def Bench.A : Prop :=
  ∀ k : ℕ, 0 < k → ∃ p : ℕ, k * k < p ∧ p < (k + 1) * (k + 1) ∧ Nat.Prime p
