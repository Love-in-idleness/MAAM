/-
Copyright (c) 2020 Patrick Stevens. All rights reserved.
Released under Apache 2.0 license as described in the file LICENSE.
Authors: Patrick Stevens, Bolton Bailey
-/

import Goal

namespace Nat

theorem _root_.Bench.proof (n : ℕ) (n_large : 512 ≤ n) :
    ∃ p : ℕ, p.Prime ∧ n < p ∧ p ≤ 2 * n := by
  have no_prime : 4 ^ n < n * n.centralBinom :=
    Nat.four_pow_lt_mul_centralBinom n (le_trans (by norm_num1) n_large)
  -- Assume there is no prime in the range.
  contrapose! no_prime
  -- Then we have the above sub-exponential bound on the size of this central binomial coefficient.
  -- We now couple this bound with an exponential lower bound on the central binomial coefficient,
  -- yielding an inequality which we have seen is false for large enough n.
  have : n.centralBinom ≤ (2 * n) ^ sqrt (2 * n) * 4 ^ (2 * n / 3) :=
    centralBinom_le_of_no_bertrand_prime n (lt_of_lt_of_le (by norm_num1) n_large) no_prime
  grw [this, ← mul_assoc, bertrand_main_inequality n_large]

end Nat
