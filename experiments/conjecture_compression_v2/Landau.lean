import Goal

def Bench.A : Prop := ∀ n : ℕ, ∃ k : ℕ, n ≤ k ∧ Nat.Prime (k * k + 1)
