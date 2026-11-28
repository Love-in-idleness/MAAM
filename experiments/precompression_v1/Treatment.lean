import Candidate

namespace Calibration

theorem one : GoalOne := by
  intro P Q hp hq
  exact keep P Q hp hq

theorem two : GoalTwo := by
  intro P Q R hp hq hr
  exact keep P (Q ∧ R) hp (And.intro hq hr)

end Calibration
