/-
MAAM reference exporter for Lean 4.24.0.
Counts const and Sort occurrences, following ABFM (2603.20396) §3.1.
The Python release's reference-length mode is NOT the paper's source-token mode.
Local compilation was unavailable in the authoring environment; the dedicated
Lean smoke workflow is provided to check this adapter on the pinned toolchain.
-/
import Lean

open Lean

namespace MAAM

abbrev Counts := Std.HashMap Name Nat
def sortName : Name := Name.mkSimple "@Sort"

def bump (counts : Counts) (name : Name) : Counts :=
  counts.insert name (counts.getD name 0 + 1)

partial def collect (expr : Expr) (counts : Counts := {}) : Counts :=
  match expr with
  | .const name _ => bump counts name
  | .sort _ => bump counts sortName
  | .app f a => collect a (collect f counts)
  | .lam _ type body _ => collect body (collect type counts)
  | .forallE _ type body _ => collect body (collect type counts)
  | .letE _ type value body _ => collect body (collect value (collect type counts))
  | .mdata _ value => collect value counts
  | .proj _ _ value => collect value counts
  | _ => counts

def refsJson (counts : Counts) : Json :=
  Json.mkObj (counts.toList.map fun (name, count) => (name.toString, toJson count))

structure Config where
  moduleName : String := ""
  output : String := ""
  prefixes : List String := []
  targets : List String := []

def parseArgs : List String → Config → Except String Config
  | [], cfg => .ok cfg
  | "--module" :: value :: rest, cfg => parseArgs rest { cfg with moduleName := value }
  | "--output" :: value :: rest, cfg => parseArgs rest { cfg with output := value }
  | "--expand-prefix" :: value :: rest, cfg => parseArgs rest { cfg with prefixes := cfg.prefixes ++ [value] }
  | "--target" :: value :: rest, cfg => parseArgs rest { cfg with targets := cfg.targets ++ [value] }
  | _, _ => .error "expected --module M --output FILE [--expand-prefix P] [--target DECL]"

def moduleOf (env : Environment) (name : Name) : String :=
  match env.getModuleIdxFor? name with
  | none => ""
  | some idx => env.header.moduleNames[idx.toNat]!.toString

def matchesPrefix (text modulePrefix : String) : Bool :=
  text == modulePrefix || text.startsWith (modulePrefix ++ ".")

def inScope (env : Environment) (cfg : Config) (name : Name) : Bool :=
  cfg.prefixes.any (matchesPrefix (moduleOf env name))

def kindOf (info : ConstantInfo) : String :=
  match info with
  | .thmInfo _ => "theorem"
  | .axiomInfo _ => "axiom"
  | _ => "definition"

def exportCorpus (env : Environment) (cfg : Config) : IO Json := do
  let roots := if cfg.targets.isEmpty then
      env.constants.toList.filterMap fun (name, _) => if inScope env cfg name then some name else none
    else cfg.targets.map String.toName
  if roots.isEmpty then throw <| IO.userError "no declarations match the requested module scope"
  let rootSet : Std.HashSet Name := roots.foldl (fun seen n => seen.insert n) {}
  let mut queue := roots.toArray
  let mut seen : Std.HashSet Name := {}
  let mut nodes : Array Json := #[]
  while !queue.isEmpty do
    let name := queue.back!
    queue := queue.pop
    if seen.contains name then continue
    seen := seen.insert name
    if name == sortName then
      nodes := nodes.push <| Json.mkObj [("name", toJson name.toString), ("kind", toJson "primitive")]
      continue
    let some info := env.find? name
      | throw <| IO.userError s!"unknown declaration: {name}"
    -- Explicit roots are expanded even if they are in Lean core. Other core
    -- declarations are the stated primitive boundary, rather than missing data.
    let primitive := info.isUnsafe || !(inScope env cfg name || rootSet.contains name)
    if primitive then
      nodes := nodes.push <| Json.mkObj [
        ("name", toJson name.toString), ("kind", toJson "primitive"),
        ("admitted", toJson (info.isUnsafe || name.toString == "sorryAx")),
        ("domain", toJson (moduleOf env name))]
      continue
    let sig := collect info.type
    let body := info.value? (allowOpaque := true) |>.map (fun expr => collect expr)
    for (dep, _) in sig.toList do queue := queue.push dep
    if let some refs := body then
      for (dep, _) in refs.toList do queue := queue.push dep
    nodes := nodes.push <| Json.mkObj [
      ("name", toJson name.toString), ("kind", toJson (kindOf info)),
      ("signature", refsJson sig), ("body", body.map refsJson |>.getD Json.null),
      ("domain", toJson (moduleOf env name)),
      ("admitted", toJson (name.toString == "sorryAx"))]
  return Json.mkObj [
    ("schema_version", toJson (1 : Nat)),
    ("corpus_id", toJson ("lean:" ++ cfg.moduleName)),
    ("length_basis", toJson "references"),
    ("provenance", Json.mkObj [
      ("kind", toJson "lean_export"), ("lean_version", toJson Lean.versionString),
      ("module", toJson cfg.moduleName), ("targets", toJson cfg.targets),
      ("expand_module_prefixes", toJson cfg.prefixes),
      ("scope", toJson (if cfg.targets.isEmpty then "all declarations in selected imported module prefixes"
                        else "target dependency closure; not a representative comparison corpus")),
      ("primitive_policy", toJson "Sort, out-of-scope declarations and unsafe declarations are explicit primitive boundaries"),
      ("source_token_counts", Json.null)]),
    ("nodes", Json.arr nodes)]

end MAAM

def main (args : List String) : IO UInt32 := do
  let cfg ← match MAAM.parseArgs args {} with
    | .ok value => pure value
    | .error message => throw <| IO.userError message
  if cfg.moduleName.isEmpty || cfg.output.isEmpty then
    throw <| IO.userError "--module and --output are required"
  let cfg := if cfg.prefixes.isEmpty then { cfg with prefixes := [cfg.moduleName] } else cfg
  initSearchPath (← findSysroot)
  let env ← importModules #[{ module := cfg.moduleName.toName }] {}
  let corpus ← MAAM.exportCorpus env cfg
  IO.FS.writeFile cfg.output corpus.compress
  return 0
