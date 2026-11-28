import Base

namespace Calibration

theorem one : GoalOne := by
  intro P Q hp hq
  exact (And.intro hp hq).left

theorem two : GoalTwo := by
  intro P Q R hp hq hr
  exact (And.intro (And.intro hp hq) hr).left.left

end Calibration
