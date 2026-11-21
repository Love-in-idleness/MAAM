import Goal

def Bench.A : Prop :=
  ∀ k : ℕ, 1 < k → ∃ p q : ℕ, Nat.Prime p ∧ Nat.Prime q ∧ p + q = k + k
