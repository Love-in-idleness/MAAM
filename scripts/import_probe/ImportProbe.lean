import Lean
open Lean
namespace MAAMPaper
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

end MAAMPaper

unsafe def main (args : List String) : IO UInt32 := do
  initSearchPath (← findSysroot)
  enableInitializersExecution
  let env ← importModules #[{module := (args.headD "Mathlib").toName}] {} (leakEnv := true) (loadExts := true)
  for owner in #["Mathlib.Order.Basic", "Mathlib.Tactic.NormNum.Basic", "Mathlib.AlgebraicGeometry.AffineTransitionLimit", "Mathlib.Order.Interval.Set.Basic", "Mathlib.Algebra.Quaternion", "Mathlib.Topology.Separation.Basic", "Mathlib.ModelTheory.Syntax", "Mathlib.Topology.VectorBundle.Basic", "Mathlib.Analysis.Calculus.BumpFunction.Normed", "Mathlib.Analysis.Real.Hyperreal"] do
    let path := System.FilePath.mk ((owner.replace "." "/") ++ ".lean")
    let source ← MAAMPaper.parseSource env path.toString (← IO.FS.readFile path)
    IO.println <| (Json.mkObj [("module", toJson owner), ("context_error", toJson source.contextError),
      ("parse_failures", toJson source.failures.size), ("tokens", toJson source.starts.size)]).compress
    for target in #[`AlgebraicGeometry.Scheme.exists_hom_hom_comp_eq_comp_of_locallyOfFiniteType,
      `VectorBundleCore.isOpenMap_proj, `ContDiffBump.integrable, `Hyperreal.infinitesimal_zero] do
      let some moduleIdx := env.getModuleIdxFor? target | continue
      if env.header.moduleNames[moduleIdx.toNat]!.toString != owner then continue
      IO.println <| (Json.mkObj [("target", toJson target.toString), ("source", MAAMPaper.sourceData env target source)]).compress
  MAAMPaper.checkParser env
  return 0
