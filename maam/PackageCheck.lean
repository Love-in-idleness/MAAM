/- Audit a freshly compiled, isolated theory-package experiment on Lean 4.24.0. -/
import Lean

open Lean
set_option maxRecDepth 10000

namespace MAAMPackage

structure Target where
  name : String
  expected : String
  deriving FromJson

structure SourceFile where
  moduleName : String
  path : String
  deriving FromJson

structure Config where
  moduleName : String
  allowedModules : List String
  auditedModules : List String
  allowedAxioms : List String
  packageModules : List String
  requiredDeclarations : List String
  targets : List Target
  sources : List SourceFile
  deriving FromJson

def moduleOf (env : Environment) (name : Name) : String :=
  match env.getModuleIdxFor? name with
  | none => ""
  | some i => env.header.moduleNames[i.toNat]!.toString

def prefixMatches (name prefix : String) : Bool :=
  name == prefix || name.startsWith (prefix ++ ".")

def exprStats (root : Expr) : Except String (Nat × List Name) := do
  let mut pending := #[root]
  let mut size := 0
  let mut names : Std.HashSet Name := {}
  while !pending.isEmpty do
    let e := pending.back!
    pending := pending.pop
    match e with
    | .mdata _ value => pending := pending.push value
    | _ =>
      size := size + 1
      if size > 1000000 then throw "expression traversal exceeded one million constructor visits"
      match e with
      | .const name _ => names := names.insert name
      | .app f x => pending := pending.push f |>.push x
      | .lam _ type body _ | .forallE _ type body _ =>
        pending := pending.push type |>.push body
      | .letE _ type value body _ =>
        pending := pending.push type |>.push value |>.push body
      | .proj _ _ value => pending := pending.push value
      | _ => pure ()
  return (size, names.toList)

partial def leaves : Syntax → Array Nat
  | .missing => #[]
  | .atom (.original _ pos _ _) _ => #[pos.byteIdx]
  | .ident (.original _ pos _ _) _ _ _ => #[pos.byteIdx]
  | .node _ kind args =>
    if kind.toString.endsWith ".docComment" || kind.toString.endsWith ".moduleDoc" then #[]
    else args.foldl (fun a s => a ++ leaves s) #[]
  | _ => #[]

def unique (a : Array Nat) : Array Nat := Id.run do
  let mut result := #[]
  for p in a.qsort (· < ·) do
    if result.back? != some p then result := result.push p
  return result

partial def findSimpleValue (stx : Syntax) : Option Syntax :=
  if stx.getKind.toString == "Lean.Parser.Command.declValSimple" then some stx
  else stx.getArgs.findSome? findSimpleValue

structure ParsedSource where
  map : FileMap
  commands : Array Syntax
  starts : Array Nat

def parseSource (env : Environment) (path source : String) : IO ParsedSource := do
  let inputCtx := Parser.mkInputContext source path
  let (header, initial, messages) ← Parser.parseHeader inputCtx
  if messages.hasErrors then throw <| IO.userError s!"source header failed: {path}"
  let action : Lean.Elab.Frontend.FrontendM (Array Syntax) := do
    let mut commands := #[]
    repeat
      Lean.Elab.Frontend.updateCmdPos
      let state ← Lean.Elab.Frontend.getCommandState
      let old ← Lean.Elab.Frontend.getParserState
      let scope := state.scopes.head!
      let (cmd, next, msgs) := Parser.parseCommand inputCtx
        { env := state.env, options := scope.opts, currNamespace := scope.currNamespace,
          openDecls := scope.openDecls } old {}
      if msgs.hasErrors || next.recovering then
        throwError "source command failed to parse"
      Lean.Elab.Frontend.setParserState next
      Lean.Elab.Frontend.setMessages {}
      commands := commands.push cmd
      if ["Lean.Parser.Command.namespace", "Lean.Parser.Command.section",
          "Lean.Parser.Command.end", "Lean.Parser.Command.open",
          "Lean.Parser.Command.set_option"].contains cmd.getKind.toString then
        Lean.Elab.Frontend.elabCommandAtFrontend cmd
        if (← Lean.Elab.Frontend.getCommandState).messages.hasErrors then
          throwError "source context replay failed"
        Lean.Elab.Frontend.setMessages {}
      if Parser.isTerminalCommand cmd then break
      if next.pos <= old.pos then throwError "source parser made no progress"
    return commands
  let (commands, _) ← (action.run { inputCtx }).run
    { commandState := Lean.Elab.Command.mkState env {} {}, parserState := initial, cmdPos := 0 }
  let starts := unique <| commands.foldl (fun a cmd => a ++ leaves cmd) (leaves header)
  return { map := inputCtx.fileMap, commands, starts }

def sourceSplit (env : Environment) (name : Name) (source : ParsedSource) : IO Json := do
  let range := declRangeExt.find? (level := .exported) env name <|>
    declRangeExt.find? (level := .server) env name
  let some range := range | throw <| IO.userError s!"no source range for {name}"
  let selected := (source.map.ofPosition range.selectionRange.pos).byteIdx
  for cmd in source.commands do
    let positions := unique (leaves cmd)
    if positions.isEmpty then continue
    if positions[0]! <= selected && selected <= positions.back! then
      let some value := findSimpleValue cmd
        | throw <| IO.userError s!"source split supports only := declarations: {name}"
      let some delimiter := value[0].getPos?
        | throw <| IO.userError s!"missing := position: {name}"
      let signature := positions.filter (· < delimiter.byteIdx)
      let body := positions.filter (· > delimiter.byteIdx)
      if signature.size + body.size + 1 != positions.size then
        throw <| IO.userError s!"source token partition failed: {name}"
      return Json.mkObj [
        ("status", toJson "parsed_simple_declaration"),
        ("signature_tokens", toJson signature.size),
        ("body_tokens", toJson body.size),
        ("declaration_tokens", toJson positions.size),
        ("separator_tokens", toJson (1 : Nat))]
  throw <| IO.userError s!"source command not found: {name}"

def audit (env : Environment) (cfg : Config) : IO Json := do
  let modules := env.header.moduleNames.toList.map Name.toString
  for mod in modules do
    if !(cfg.allowedModules.any (prefixMatches mod)) then
      throw <| IO.userError s!"forbidden imported module: {mod}"
  for declaration in cfg.requiredDeclarations do
    let name := declaration.toName
    if (env.find? name).isNone || !(cfg.packageModules.contains (moduleOf env name)) then
      throw <| IO.userError s!"missing package declaration: {declaration}"
  let mut queue : Array Name := #[]
  for (name, _) in env.constants.toList do
    if cfg.auditedModules.contains (moduleOf env name) then queue := queue.push name
  for target in cfg.targets do
    queue := queue.push target.name.toName |>.push target.expected.toName
  let mut seen : Std.HashSet Name := {}
  let mut axioms : List String := []
  while !queue.isEmpty do
    let name := queue.back!
    queue := queue.pop
    if seen.contains name then continue
    seen := seen.insert name
    let some info := env.find? name | throw <| IO.userError s!"missing dependency: {name}"
    if info.isUnsafe then throw <| IO.userError s!"unsafe dependency: {name}"
    match info with
    | .axiomInfo _ =>
      if name.toString == "sorryAx" || !(cfg.allowedAxioms.contains name.toString) then
        throw <| IO.userError s!"forbidden axiom: {name}"
      axioms := name.toString :: axioms
    | _ => pure ()
    let (_, signatureNames) ← IO.ofExcept (exprStats info.type)
    queue := queue ++ signatureNames.toArray
    if let some value := info.value? (allowOpaque := true) then
      let (_, valueNames) ← IO.ofExcept (exprStats value)
      queue := queue ++ valueNames.toArray
  let mut parsed : Std.HashMap String ParsedSource := {}
  let mut files : Array Json := #[]
  for source in cfg.sources do
    let text ← IO.FS.readFile source.path
    let data ← parseSource env source.path text
    parsed := parsed.insert source.moduleName data
    files := files.push <| Json.mkObj [
      ("module", toJson source.moduleName),
      ("source_tokens", toJson data.starts.size),
      ("source_utf8_bytes", toJson text.utf8ByteSize)]
  let mut targets : Array Json := #[]
  for target in cfg.targets do
    let some info := env.find? target.name.toName
      | throw <| IO.userError s!"unknown target: {target.name}"
    match info with
    | .thmInfo _ => pure ()
    | _ => throw <| IO.userError s!"target is not a theorem: {target.name}"
    let some expected := env.find? target.expected.toName
      | throw <| IO.userError s!"unknown expected proposition: {target.expected}"
    if !expected.levelParams.isEmpty then
      throw <| IO.userError "reference protocol requires a monomorphic goal declaration"
    let check : MetaM Bool := do
      if !(← Meta.isProp (mkConst target.expected.toName)) then return false
      Meta.isDefEq info.type (mkConst target.expected.toName)
    let (same, _, _) ← check.toIO
      { fileName := "<package-goal-check>", fileMap := default } { env }
    if !same then throw <| IO.userError s!"target proposition changed: {target.name}"
    let (signatureSize, _) ← IO.ofExcept (exprStats info.type)
    let some value := info.value? (allowOpaque := true)
      | throw <| IO.userError s!"theorem has no proof: {target.name}"
    let (bodySize, directRefs) ← IO.ofExcept (exprStats value)
    let mod := moduleOf env target.name.toName
    let some source := parsed.get? mod
      | throw <| IO.userError s!"missing target source: {mod}"
    let split ← sourceSplit env target.name.toName source
    targets := targets.push <| Json.mkObj [
      ("name", toJson target.name), ("expected", toJson target.expected),
      ("goal_preserved", toJson true), ("signature_expr_nodes", toJson signatureSize),
      ("proof_expr_nodes", toJson bodySize),
      ("direct_proof_dependencies", toJson (directRefs.map Name.toString |>.mergeSort (· < ·))),
      ("source", split)]
  return Json.mkObj [
    ("lean_version", toJson Lean.versionString),
    ("module", toJson cfg.moduleName),
    ("imported_modules", toJson (modules.mergeSort (· < ·))),
    ("audited_declarations", toJson seen.size),
    ("package_declarations", toJson cfg.requiredDeclarations),
    ("axioms_used", toJson (axioms.mergeSort (· < ·))),
    ("targets", Json.arr targets), ("sources", Json.arr files),
    ("verification", toJson "freshly_compiled_theorems_and_dependency_audit")]

end MAAMPackage

unsafe def main (args : List String) : IO UInt32 := do
  let [input, output] := args
    | throw <| IO.userError "usage: PackageCheck.lean INPUT_JSON OUTPUT_JSON"
  let config ← IO.ofExcept <| Json.parse (← IO.FS.readFile input)
  let cfg : MAAMPackage.Config ← IO.ofExcept (fromJson? config)
  initSearchPath (← findSysroot)
  enableInitializersExecution
  let env ← importModules #[{ module := cfg.moduleName.toName }] {}
    (leakEnv := true) (loadExts := true)
  let result ← MAAMPackage.audit env cfg
  IO.FS.writeFile output result.pretty
  return 0
