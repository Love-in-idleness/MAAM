import Goal

def Bench.A : Prop := ∀ n : ℕ, ∃ p : ℕ, n ≤ p ∧ Nat.Prime p ∧ Nat.Prime (p + 2)
