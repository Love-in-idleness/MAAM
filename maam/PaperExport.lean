/- Fixed-snapshot, streaming replication export. No unsafe-recursion cutoffs.
   const/Sort traversal follows ABFM §3.1; source tokens use Lean's contextual command parser.
   Whole declaration ranges are measured, including the declaration header.
   Parse failures and absent/shared source ranges remain explicit missing data. -/
import Lean

open Lean
set_option maxRecDepth 1000000
set_option maxHeartbeats 0

namespace MAAMPaper

abbrev Counts := Std.HashMap Name Nat
def sortName : Name := Name.mkSimple "@Sort"
def bump (a : Counts) (n : Name) : Counts := a.insert n (a.getD n 0 + 1)
partial def collectTree (e : Expr) (a : Counts := {}) : Counts :=
  match e with
  | .const n _ => bump a n
  | .sort _ => bump a sortName
  | .app f x => collectTree x (collectTree f a)
  | .lam _ t b _ | .forallE _ t b _ => collectTree b (collectTree t a)
  | .letE _ t v b _ => collectTree b (collectTree v (collectTree t a))
  | .mdata _ x | .proj _ _ x => collectTree x a
  | _ => a

def children : Expr → Array Expr
  | .app f x => #[f, x]
  | .lam _ t b _ | .forallE _ t b _ => #[t, b]
  | .letE _ t v b _ => #[t, v, b]
  | .mdata _ x | .proj _ _ x => #[x]
  | _ => #[]

def collectShared (root : Expr) : Counts := Id.run do
  -- Structural equality includes metadata wrappers: using Expr.eqv here could
  -- identify a wrapper with its child and create a spurious self-edge.
  let mut seen : Std.HashSet ExprStructEq := {}
  let mut pending : Array (Expr × Bool) := #[(root, false)]
  let mut order : Array Expr := #[]
  while !pending.isEmpty do
    let (e, finish) := pending.back!
    pending := pending.pop
    if finish then
      order := order.push e
    else if !(seen.contains ⟨e⟩) then
      seen := seen.insert ⟨e⟩
      pending := pending.push (e, true)
      for child in children e do pending := pending.push (child, false)
  let mut multiplicity : Std.HashMap ExprStructEq Nat := ({} : Std.HashMap ExprStructEq Nat).insert ⟨root⟩ 1
  let mut result : Counts := {}
  for e in order.reverse do
    let count := multiplicity.getD ⟨e⟩ 0
    match e with
    | .const name _ => result := result.insert name (result.getD name 0 + count)
    | .sort _ => result := result.insert sortName (result.getD sortName 0 + count)
    | _ =>
      for child in children e do
        let key : ExprStructEq := ⟨child⟩
        multiplicity := multiplicity.insert key (multiplicity.getD key 0 + count)
  return result

def collect (root : Expr) : Counts := Id.run do
  -- Most declarations are small. Bound the ordinary tree walk so a compact
  -- shared Expr cannot require exponentially many physical visits.
  let mut pending := #[root]
  let mut result : Counts := {}
  let mut steps := 0
  while !pending.isEmpty && steps < 4096 do
    let e := pending.back!
    pending := pending.pop
    steps := steps + 1
    match e with
    | .const name _ => result := bump result name
    | .sort _ => result := bump result sortName
    | _ =>
      for child in children e do pending := pending.push child
  return if pending.isEmpty then result else collectShared root

def checkCounts : IO Unit := do
  let leaf := Expr.const `MAAMCountingTest.leaf []
  let sortExpr := Expr.sort .zero
  let sample := Expr.letE `x sortExpr (Expr.app leaf (Expr.mdata {} leaf))
    (Expr.lam `y sortExpr (Expr.forallE `z sortExpr (Expr.proj `Ignored 0 leaf) .default) .default) false
  let same (a b : Counts) := a.size == b.size && a.toList.all (fun (n, k) => b.getD n 0 == k)
  if !(same (collectTree sample) (collectShared sample)) || !(same (collectTree sample) (collect sample)) then
    throw <| IO.userError "shared-expression reference counts disagree with the paper's tree walk"
  let counts := collect sample
  if counts.getD `MAAMCountingTest.leaf 0 != 3 || counts.getD sortName 0 != 3 || counts.size != 2 then
    throw <| IO.userError "expression constructor occurrence check failed"
  let mut shared := leaf
  for _ in [:80] do shared := Expr.app shared shared
  let counts := collect shared
  if counts.size != 1 || counts.getD `MAAMCountingTest.leaf 0 != (2 : Nat)^80 then
    throw <| IO.userError "shared-expression stress check failed"
  IO.eprintln "Expression occurrence checks passed, including an 81-node DAG with 2^80 references"

def refsJson (a : Counts) : Json :=
  Json.mkObj (a.toList.map fun (n, k) => (n.toString, toJson k))

def progress (message : String) : IO Unit := do
  if let some path ← IO.getEnv "MAAM_PROGRESS_FILE" then
    IO.FS.writeFile path message

def moduleOf (env : Environment) (n : Name) : String :=
  match env.getModuleIdxFor? n with
  | none => ""
  | some i => env.header.moduleNames[i.toNat]!.toString

def inScope (env : Environment) (scope : String) (n : Name) : Bool :=
  let m := moduleOf env n
  m == scope || m.startsWith (scope ++ ".")

structure ParseFailure where
  startByte : Nat
  endByte : Nat
  message : String
  deriving Inhabited

structure Source where
  map : FileMap
  starts : Array Nat
  coreStarts : Array Nat
  failures : Array ParseFailure := #[]
  contextError : Option String := none
  deriving Inhabited

partial def leaves (stx : Syntax) (omitModifiers := false) : Array Nat :=
  match stx with
  | .missing => #[]
  | .atom (.original _ pos _ _) _ => #[pos.byteIdx]
  | .ident (.original _ pos _ _) _ _ _ => #[pos.byteIdx]
  | .node _ kind args =>
    if kind.toString.endsWith ".docComment" || kind.toString.endsWith ".moduleDoc" || (omitModifiers && kind.toString.endsWith ".declModifiers") then #[]
    else args.foldl (fun acc s => acc ++ leaves s omitModifiers) #[]
  | _ => #[]

def uniqueStarts (starts : Array Nat) : Array Nat := Id.run do
  let mut result : Array Nat := #[]
  for pos in starts.qsort (· < ·) do
    if result.back? != some pos then result := result.push pos
  return result

partial def hasLocalModifier : Syntax → Bool
  | .node _ kind args => kind == `Lean.Parser.Term.local || args.any hasLocalModifier
  | _ => false

-- Replay only parser context: proofs and definitions are never re-elaborated.
-- Global/scoped syntax is already present in the imported fixed environment;
-- namespace/open/section/end and local syntax commands restore file context.
def parseSource (env : Environment) (fileName source : String) : IO Source := do
  let inputCtx := Parser.mkInputContext source fileName
  let (_, initial, headerMessages) ← Parser.parseHeader inputCtx
  let action : Lean.Elab.Frontend.FrontendM Source := do
    let mut starts : Array Nat := #[]
    let mut coreStarts : Array Nat := #[]
    let mut failures : Array ParseFailure := #[]
    let mut contextError := if headerMessages.hasErrors then some "module header parse failed" else none
    repeat
      Lean.Elab.Frontend.updateCmdPos
      let state ← Lean.Elab.Frontend.getCommandState
      let oldState ← Lean.Elab.Frontend.getParserState
      let scope := state.scopes.head!
      let (cmd, next, messages) := Parser.parseCommand inputCtx
        { env := state.env, options := scope.opts, currNamespace := scope.currNamespace, openDecls := scope.openDecls } oldState {}
      Lean.Elab.Frontend.setParserState next
      Lean.Elab.Frontend.setMessages {}
      let kind := cmd.getKind.toString
      let text := (source.extract (cmd.getPos?.getD oldState.pos) (cmd.getTailPos?.getD next.pos)).trim
      let commandStarts := uniqueStarts (leaves cmd)
      let commandStart := commandStarts[0]?.getD oldState.pos.byteIdx
      let commandFailed := next.recovering || messages.toList.any (fun msg =>
        msg.severity == .error && (inputCtx.fileMap.ofPosition msg.pos).byteIdx >= commandStart)
      if messages.hasErrors then
        failures := failures.push
          { startByte := oldState.pos.byteIdx
            endByte := if commandFailed then next.pos.byteIdx else commandStart
            message := s!"command parse failed at line {(inputCtx.fileMap.toPosition oldState.pos).line}; kind={kind}" }
        if ["local ", "open ", "namespace ", "section", "noncomputable section", "end"].any text.startsWith then
          contextError := some "a parser-context command failed to parse"
      if !commandFailed then
        starts := starts ++ commandStarts
        coreStarts := coreStarts ++ leaves cmd true
        let localSyntax := (kind.endsWith ".notation" || kind.endsWith ".mixfix" || kind.endsWith ".syntax") && hasLocalModifier cmd
        if ["Lean.Parser.Command.namespace", "Lean.Parser.Command.section", "Lean.Parser.Command.end", "Lean.Parser.Command.open", "Lean.Parser.Command.set_option"].contains kind || localSyntax then
          Lean.Elab.Frontend.elabCommandAtFrontend cmd
          if (← Lean.Elab.Frontend.getCommandState).messages.hasErrors then
            contextError := some s!"parser context replay failed: {kind}"
          Lean.Elab.Frontend.setMessages {}
      if Parser.isTerminalCommand cmd then break
      if next.pos <= oldState.pos then
        contextError := some "command parser made no progress"
        break
    return { map := inputCtx.fileMap, starts := uniqueStarts starts, coreStarts := uniqueStarts coreStarts, failures, contextError }
  let (result, _) ← (action.run { inputCtx }).run
    { commandState := Lean.Elab.Command.mkState env {} {}, parserState := initial, cmdPos := 0 }
  return result

def lowerBound (a : Array Nat) (value : Nat) : Nat := Id.run do
  let mut low := 0
  let mut high := a.size
  while low < high do
    let mid := (low + high) / 2
    if a[mid]! < value then low := mid + 1 else high := mid
  return low

def checkParser (env : Environment) : IO Unit := do
  let examples : List (String × Nat) := [
    ("theorem isOpenMap_proj : IsOpenMap Z.proj := Z.toFiberBundleCore.isOpenMap_proj", 7),
    ("theorem integrable : Integrable f μ := f.continuous.integrable_of_hasCompactSupport f.hasCompactSupport", 9),
    ("theorem infinitesimal_zero : Infinitesimal 0 := isSt_refl_real 0", 8),
    ("/- outer /- nested -/ -/ /-- docs -/ theorem tiny : P := Q -- trailing", 6),
    ("def text : String := \"a b /- c -/\"", 6)]
  for (text, expected) in examples do
    let parsed ← IO.ofExcept <| Parser.runParserCategory env `command text
    let count := (uniqueStarts (leaves parsed)).size
    if count != expected then
      throw <| IO.userError s!"Lean parser token check failed: expected {expected}, got {count}: {text}"
  let fixture := "namespace MAAMSourceCheck\n@[inherit_doc] local infix:50 \" ≺ \" => LT.lt\ntheorem localTest (a b : Nat) (h : a ≺ b) : a < b := h\ndef field (x : Nat × Nat) := x.1.eq_self\ndef text := s!\"\\{ {repr (1, 2).1} }\"\nend MAAMSourceCheck"
  let source ← parseSource env "parser-check" fixture
  if source.contextError.isSome || !source.failures.isEmpty || source.starts.isEmpty then
    throw <| IO.userError "contextual parser check failed on local notation, numeric field access, or string interpolation"
  let recovery ← parseSource env "recovery-check" "theorem beforeError : True := True.intro\n#maam_invalid_syntax\ntheorem afterError : True := True.intro"
  if recovery.contextError.isSome || recovery.failures.isEmpty || !(recovery.starts.any (· > 70)) then
    throw <| IO.userError "source parser failed to isolate an invalid command from later declarations"
  let protectedSyntax ← IO.ofExcept <| Parser.runParserCategory env `command "protected theorem integrable : Integrable f μ := f.continuous.integrable_of_hasCompactSupport f.hasCompactSupport"
  if (uniqueStarts (leaves protectedSyntax)).size != 10 || (uniqueStarts (leaves protectedSyntax true)).size != 9 then
    throw <| IO.userError "declaration modifier sensitivity check failed"
  IO.eprintln "Contextual source-parser checks passed"

def sourceData (env : Environment) (name : Name) (source : Source) : Json := Id.run do
  let range := declRangeExt.find? (level := .exported) env name <|>
    declRangeExt.find? (level := .server) env name
  let some range := range | return Json.mkObj [("status", toJson "no_declaration_range")]
  if let some err := source.contextError then
    return Json.mkObj [("status", toJson "source_context_error"), ("error", toJson err)]
  let startPos := source.map.ofPosition range.range.pos
  let stopPos := source.map.ofPosition range.range.endPos
  for failure in source.failures do
    if failure.startByte < stopPos.byteIdx && startPos.byteIdx < failure.endByte then
      return Json.mkObj [("status", toJson "source_parse_error"), ("error", toJson failure.message)]
  let selectedStart := source.map.ofPosition range.selectionRange.pos
  let selectedEnd := source.map.ofPosition range.selectionRange.endPos
  let selected := source.map.source.extract selectedStart selectedEnd
  let userName := (privateToUserName name.eraseMacroScopes).toString
  let named := selected == userName || userName.endsWith ("." ++ selected)
  let count := lowerBound source.starts stopPos.byteIdx - lowerBound source.starts startPos.byteIdx
  return Json.mkObj [
    ("status", toJson (if named && !selected.isEmpty then "named_source" else "shared_or_generated_source")),
    ("tokens", toJson count),
    ("tokens_without_modifiers", toJson (lowerBound source.coreStarts stopPos.byteIdx - lowerBound source.coreStarts startPos.byteIdx)),
    ("selected_name", toJson selected),
    ("start_line", toJson range.range.pos.line), ("end_line", toJson range.range.endPos.line),
    ("start_byte", toJson startPos.byteIdx), ("end_byte", toJson stopPos.byteIdx)]

def kindOf (info : ConstantInfo) : String :=
  match info with
  | .thmInfo _ => "theorem"
  | .axiomInfo _ => "axiom"
  | _ => "definition"

def exportAll (env : Environment) (mod scope sourceRoot output revision : String) : IO Unit := do
  let moduleNames := env.header.moduleNames.map Name.toString
  let scopedModules := moduleNames.map fun m => m == scope || m.startsWith (scope ++ ".")
  let isScoped := fun n => (env.getModuleIdxFor? n).any fun i => scopedModules[i.toNat]!
  let roots := env.constants.toList.filterMap fun (n, _) => if isScoped n then some n else none
  if roots.isEmpty then throw <| IO.userError "empty module scope"
  progress s!"exporting; vertices=0; roots={roots.length}"
  let handle ← IO.FS.Handle.mk output .write
  handle.putStrLn <| (Json.mkObj [
    ("record", toJson "metadata"), ("schema_version", toJson (1 : Nat)),
    ("module", toJson mod), ("scope", toJson scope), ("revision", toJson revision),
    ("lean_version", toJson Lean.versionString),
    ("import_policy", toJson "initializers enabled; imported environment persistent until process exit"),
    ("primitive_policy", toJson "Sort and out-of-scope declarations only; unsafe definitions retained"),
    ("token_policy", toJson "distinct original syntax-leaf starts in declaration ranges; parser context replay; comments excluded; named/shared source and modifier sensitivity separate"),
    ("root_count", toJson roots.length)]).compress
  let mut queue := roots.toArray
  let mut seen : Std.HashSet Name := {}
  let mut sources : Std.HashMap String Source := {}
  let mut done := 0
  while !queue.isEmpty do
    let name := queue.back!
    queue := queue.pop
    if seen.contains name then continue
    seen := seen.insert name
    if name == sortName then
      handle.putStrLn <| (Json.mkObj [("record", toJson "node"), ("name", toJson name.toString),
        ("kind", toJson "primitive"), ("signature", Json.mkObj []), ("body", Json.null)]).compress
      continue
    let some info := env.find? name | throw <| IO.userError s!"unknown declaration {name}"
    let moduleName := (env.getModuleIdxFor? name).map (fun i => moduleNames[i.toNat]!) |>.getD ""
    let primitive := !(isScoped name)
    let sig := if primitive then ({} : Counts) else collect info.type
    let body := if primitive then none else info.value? (allowOpaque := true) |>.map (fun e => collect e)
    for (dep, _) in sig.toList do queue := queue.push dep
    if let some refs := body then
      for (dep, _) in refs.toList do queue := queue.push dep
    let mut source := Json.mkObj [("status", toJson "primitive")]
    if !primitive then
      if !(sources.contains moduleName) then
        let path := System.FilePath.mk sourceRoot / ((moduleName.replace "." "/") ++ ".lean")
        if ← path.pathExists then
          let text ← IO.FS.readFile path
          sources := sources.insert moduleName (← parseSource env path.toString text)
        else
          sources := sources.insert moduleName { map := FileMap.ofString "", starts := #[], coreStarts := #[], contextError := some "source_file_missing" }
      source := sourceData env name (sources[moduleName]!)
    handle.putStrLn <| (Json.mkObj [
      ("record", toJson "node"), ("name", toJson name.toString),
      ("kind", toJson (if primitive then "primitive" else kindOf info)),
      ("module", toJson moduleName), ("unsafe", toJson info.isUnsafe),
      ("signature", refsJson sig), ("body", body.map refsJson |>.getD Json.null),
      ("source", source)]).compress
    done := done + 1
    if done % 1000 == 0 then progress s!"exporting; vertices={seen.size}; modules={sources.size}"
    if done % 25000 == 0 then IO.eprintln s!"Exported {done} declarations"
  handle.flush
  progress s!"complete; vertices={seen.size}; modules={sources.size}"
  IO.eprintln s!"Finished: {seen.size} vertices; {sources.size} source modules"

end MAAMPaper

unsafe def main (args : List String) : IO UInt32 := do
  let [mod, scope, sourceRoot, output, revision] := args
    | throw <| IO.userError "usage: PaperExport.lean MODULE MODULE_PREFIX SOURCE_ROOT OUTPUT_JSONL REVISION"
  initSearchPath (← findSysroot)
  enableInitializersExecution
  MAAMPaper.progress "importing environment"
  let env ← importModules #[{ module := mod.toName }] {} (leakEnv := true) (loadExts := true)
  MAAMPaper.progress "environment loaded; checking occurrence counts and source parser"
  MAAMPaper.checkCounts
  MAAMPaper.checkParser env
  MAAMPaper.exportAll env mod scope sourceRoot output revision
  return 0
