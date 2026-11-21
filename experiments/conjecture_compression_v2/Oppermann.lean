import Goal

def Bench.A : Prop :=
  ∀ k : ℕ, 1 < k →
    (∃ p : ℕ, k * (k - 1) < p ∧ p < k * k ∧ Nat.Prime p) ∧
    (∃ q : ℕ, k * k < q ∧ q < k * (k + 1) ∧ Nat.Prime q)
