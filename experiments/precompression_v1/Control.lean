import Base

namespace Calibration

theorem one : GoalOne := by
  intro P Q hp hq
  exact hp

theorem two : GoalTwo := by
  intro P Q R hp hq hr
  exact hp

end Calibration
