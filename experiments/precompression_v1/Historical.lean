import Base

namespace Calibration

theorem one : GoalOne := by
  intro P Q hp hq
  have combined : P ∧ Q := And.intro hp hq
  have first : P := combined.left
  exact first

theorem two : GoalTwo := by
  intro P Q R hp hq hr
  have combined : (P ∧ Q) ∧ R := And.intro (And.intro hp hq) hr
  have firstPair : P ∧ Q := combined.left
  have first : P := firstPair.left
  exact first

end Calibration
