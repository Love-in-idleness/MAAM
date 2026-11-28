import Mathlib.Data.Nat.Factorial.Basic
import Mathlib.Data.Nat.Prime.Defs
import Mathlib.Order.Bounds.Basic

def Bench.B : Prop := ∀ n : ℕ, ∃ p : ℕ, n ≤ p ∧ Nat.Prime p
