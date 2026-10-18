/- Measure all declarations in charged modules, including compiler auxiliaries. -/
import Lean

open Lean
set_option maxRecDepth 10000

namespace MAAMInventory

structure Config where
  moduleName : String
  allowedModules : List String
  chargedModules : List String
  deriving FromJson

def moduleOf (env : Environment) (name : Name) : String :=
  match env.getModuleIdxFor? name with
  | none => ""
  | some i => env.header.moduleNames[i.toNat]!.toString

def prefixMatches (name scopePrefix : String) : Bool :=
  name == scopePrefix || name.startsWith (scopePrefix ++ ".")

def exprStats (root : Expr) : Except String (Nat × List Name) := do
  let mut pending := #[root]
  let mut size := 0
  let mut refs : Std.HashSet Name := {}
  while !pending.isEmpty do
    let e := pending.back!
    pending := pending.pop
    match e with
    | .mdata _ value => pending := pending.push value
    | _ =>
      size := size + 1
      if size > 1000000 then throw "inventory expression traversal exceeded one million visits"
      match e with
      | .const name _ => refs := refs.insert name
      | .app f x => pending := pending.push f |>.push x
      | .lam _ type body _ | .forallE _ type body _ =>
        pending := pending.push type |>.push body
      | .letE _ type value body _ =>
        pending := pending.push type |>.push value |>.push body
      | .proj _ _ value => pending := pending.push value
      | _ => pure ()
  return (size, refs.toList)

def kind (info : ConstantInfo) : String :=
  match info with
  | .axiomInfo _ => "axiom"
  | .defnInfo _ => "definition"
  | .thmInfo _ => "theorem"
  | .opaqueInfo _ => "opaque"
  | .quotInfo _ => "quotient"
  | .inductInfo _ => "inductive"
  | .ctorInfo _ => "constructor"
  | .recInfo _ => "recursor"

def inventory (env : Environment) (cfg : Config) : IO Json := do
  let modules := env.header.moduleNames.toList.map Name.toString
  for mod in modules do
    if !(cfg.allowedModules.any (prefixMatches mod)) then
      throw <| IO.userError s!"forbidden inventory import: {mod}"
  let mut result : Array Json := #[]
  for mod in cfg.chargedModules do
    if !(modules.contains mod) then throw <| IO.userError s!"charged module not imported: {mod}"
    let entries := env.constants.toList.filter (fun entry => moduleOf env entry.1 == mod)
      |>.mergeSort (fun a b => a.1.toString < b.1.toString)
    if entries.isEmpty then throw <| IO.userError s!"charged module has no declarations: {mod}"
    let mut declarations : Array Json := #[]
    let mut total := 0
    for (name, info) in entries do
      if info.isUnsafe then throw <| IO.userError s!"unsafe inventory declaration: {name}"
      if kind info == "axiom" then throw <| IO.userError s!"axiom in charged inventory: {name}"
      let (signature, signatureRefs) ← IO.ofExcept (exprStats info.type)
      let (value, valueRefs) ← match info.value? (allowOpaque := true) with
        | some expression => IO.ofExcept (exprStats expression)
        | none => pure (0, [])
      total := total + signature + value
      declarations := declarations.push <| Json.mkObj [
        ("name", toJson name.toString), ("kind", toJson (kind info)),
        ("signature_expr_nodes", toJson signature), ("value_expr_nodes", toJson value),
        ("direct_dependencies", toJson ((signatureRefs ++ valueRefs).map Name.toString |>.mergeSort (· < ·)))]
    result := result.push <| Json.mkObj [
      ("module", toJson mod), ("expr_nodes", toJson total),
      ("declaration_count", toJson declarations.size), ("declarations", Json.arr declarations)]
  return Json.mkObj [
    ("schema_version", toJson (1 : Nat)), ("lean_version", toJson Lean.versionString),
    ("module", toJson cfg.moduleName), ("modules", Json.arr result),
    ("convention", toJson "sum of constructor occurrences in every charged declaration type and available value; includes generated declarations; metadata wrappers excluded; constants not inlined")]

end MAAMInventory

unsafe def main (args : List String) : IO UInt32 := do
  let [input, output] := args
    | throw <| IO.userError "usage: Inventory.lean INPUT_JSON OUTPUT_JSON"
  let config ← IO.ofExcept <| Json.parse (← IO.FS.readFile input)
  let cfg : MAAMInventory.Config ← IO.ofExcept (fromJson? config)
  initSearchPath (← findSysroot)
  enableInitializersExecution
  let env ← importModules #[{ module := cfg.moduleName.toName }] {}
    (leakEnv := true) (loadExts := true)
  let result ← MAAMInventory.inventory env cfg
  IO.FS.writeFile output result.pretty
  return 0
