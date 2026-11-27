import Init

namespace Calibration

def GoalOne : Prop := ∀ (P Q : Prop), P → Q → P
def GoalTwo : Prop := ∀ (P Q R : Prop), P → Q → R → P

end Calibration
