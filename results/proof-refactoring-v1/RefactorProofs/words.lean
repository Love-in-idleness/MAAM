import Base
import Tasks.Words
import RefactorShared

namespace Submission
theorem solve_words : Tasks.words :=
by
  intro G H g h f hf w
  have hone := Refactored.shared_1 G H g h f hf
  have hinv := Refactored.shared_2 G H g h f hf hone
  induction w with
  | unit =>
      intro _
      exact hone
  | atom x =>
      intro hx
      exact hx
  | product x y ihx ihy =>
      intro hw
      change x.admissible (fun x => f x = h.one) ∧
        y.admissible (fun x => f x = h.one) at hw
      change f (g.mul (x.eval g) (y.eval g)) = h.one
      rw [hf, ihx hw.1, ihy hw.2, h.one_mul]
  | inverse x ih =>
      intro hw
      exact hinv (x.eval g) (ih hw)

end Submission
