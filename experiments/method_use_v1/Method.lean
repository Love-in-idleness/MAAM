import Base

namespace MethodUse

theorem left_factor {G : Type} (g : Foundation.Group G) (a x c : G)
    (e : g.mul a x = c) : x = g.mul (g.inv a) c := by
  have lifted := congrArg (fun z => g.mul (g.inv a) z) e
  simpa only [← g.mul_assoc, g.inv_mul, g.one_mul] using lifted

end MethodUse
