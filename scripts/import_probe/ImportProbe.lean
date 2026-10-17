import Lean
open Lean

unsafe def main (args : List String) : IO UInt32 := do
  initSearchPath (← findSysroot)
  enableInitializersExecution
  let moduleName := (args.headD "Mathlib").toName
  IO.eprintln s!"phase=import_start; module={moduleName}"
  let start ← IO.monoNanosNow
  let env ← importModules #[{module := moduleName}] {} (leakEnv := true) (loadExts := true)
  let stop ← IO.monoNanosNow
  let mut total := 0
  let mut mathlib := 0
  for (name, _) in env.constants.toList do
    total := total + 1
    if let some idx := env.getModuleIdxFor? name then
      let owner := env.header.moduleNames[idx.toNat]!.toString
      if owner == "Mathlib" || owner.startsWith "Mathlib." then mathlib := mathlib + 1
  IO.println <| (Json.mkObj [("phase", toJson "import_complete"),
    ("import_ms", toJson ((stop-start) / 1000000)),
    ("constants", toJson total), ("mathlib_constants", toJson mathlib),
    ("modules", toJson env.header.moduleNames.size)]).compress
  for name in #[`Hyperreal.infinitesimal_zero,
      `AlgebraicGeometry.Scheme.exists_hom_hom_comp_eq_comp_of_locallyOfFiniteType] do
    let range := declRangeExt.find? (level := .exported) env name <|>
      declRangeExt.find? (level := .server) env name
    IO.println <| (Json.mkObj [("name", toJson name.toString),
      ("found", toJson (env.find? name).isSome), ("source_range", toJson range.isSome)]).compress
  return 0
