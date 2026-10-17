-- Lexer instrumentation copied from maam/PaperExport.lean; only error positions added.
import Lean
open Lean
namespace ProbeLexer
partial def skipBlock (s : String) (p : String.Pos) (depth : Nat) : String.Pos :=
  if s.atEnd p then p else
  let q := s.next p
  if s.get p == '/' && s.get q == '-' then skipBlock s (s.next q) (depth + 1)
  else if s.get p == '-' && s.get q == '/' then
    if depth == 1 then s.next q else skipBlock s (s.next q) (depth - 1)
  else skipBlock s q depth

partial def skipLine (s : String) (p : String.Pos) : String.Pos :=
  if s.atEnd p || s.get p == '\n' then p else skipLine s (s.next p)

partial def skipComments (s : String) (p : String.Pos) : String.Pos :=
  if s.atEnd p then p else
  let q := s.next p
  if (s.get p).isWhitespace then skipComments s q
  else if s.get p == '-' && s.get q == '-' then skipComments s (skipLine s (s.next q))
  else if s.get p == '/' && s.get q == '-' then skipComments s (skipBlock s (s.next q) 1)
  else p

structure Source where
  map : FileMap
  starts : Array Nat
  lexicalError : Option String
  deriving Inhabited

def lexSource (env : Environment) (fileName source : String) : Source := Id.run do
  let ctx := Parser.mkInputContext source fileName
  let mut state := Parser.mkParserState ctx.inputString
  let mut starts : Array Nat := #[]
  let table := Parser.getTokenTable env
  repeat
    let pos := skipComments ctx.inputString state.pos
    if ctx.atEnd pos then break
    state := { state with pos, stxStack := .empty, errorMsg := none }
    let next := (Parser.tokenFn []).run ctx { env, options := {} } table state
    if let some err := next.errorMsg then
      return { map := ctx.fileMap, starts := #[], lexicalError := some s!"{toString err}; byte={pos.byteIdx}; lexer_pos={next.pos.byteIdx}" }
    if next.pos <= pos then
      return { map := ctx.fileMap, starts := #[], lexicalError := some "lexer made no progress" }
    starts := starts.push pos.byteIdx
    state := next
  return { map := ctx.fileMap, starts, lexicalError := none }

end ProbeLexer

namespace ProbeParser
open Lean.Elab.Frontend

partial def leaves (stx : Syntax) : Array Nat :=
  match stx with
  | .missing => #[]
  | .atom (.original _ pos _ _) _ => #[pos.byteIdx]
  | .ident (.original _ pos _ _) _ _ _ => #[pos.byteIdx]
  | .node _ kind args =>
    if kind.toString.endsWith ".docComment" || kind.toString.endsWith ".moduleDoc" then #[]
    else args.foldl (fun acc s => acc ++ leaves s) #[]
  | _ => #[]

def measure (env : Environment) (fileName source : String) : IO Json := do
  let inputCtx := Parser.mkInputContext source fileName
  let (_, initial, _) ← Parser.parseHeader inputCtx
  let action : FrontendM Json := do
    let mut tokens : Array Nat := #[]
    let mut errors : Array Json := #[]
    let mut contexts : Array Json := #[]
    let mut commands := 0
    repeat
      updateCmdPos
      let state ← getCommandState
      let ps ← getParserState
      let scope := state.scopes.head!
      let (cmd, ps, messages) := Parser.parseCommand inputCtx
        { env := state.env, options := scope.opts, currNamespace := scope.currNamespace, openDecls := scope.openDecls } ps {}
      setParserState ps
      setMessages {}
      commands := commands + 1
      if messages.hasErrors then
        if errors.size < 10 then
          errors := errors.push <| Json.mkObj [("line", toJson (inputCtx.fileMap.toPosition (cmd.getPos?.getD 0)).line), ("kind", toJson cmd.getKind.toString)]
      else
        tokens := tokens ++ leaves cmd
        let kind := cmd.getKind.toString
        let text := (source.extract (cmd.getPos?.getD 0) (cmd.getTailPos?.getD 0)).trim
        let localNotation := (kind.endsWith ".notation" || kind.endsWith ".mixfix" || kind.endsWith ".syntax") && text.startsWith "local "
        if ["Lean.Parser.Command.namespace", "Lean.Parser.Command.section", "Lean.Parser.Command.end", "Lean.Parser.Command.open"].contains kind || localNotation then
          elabCommandAtFrontend cmd
          let next ← getCommandState
          if next.messages.hasErrors && contexts.size < 10 then
            contexts := contexts.push <| Json.mkObj [("kind", toJson kind), ("text", toJson text)]
          setMessages {}
      if Parser.isTerminalCommand cmd then break
    return Json.mkObj [("commands", toJson commands), ("tokens", toJson tokens.size), ("errors", toJson errors), ("context_errors", toJson contexts)]
  let (result, _) ← (action.run { inputCtx }).run
    { commandState := Lean.Elab.Command.mkState env {} {}, parserState := initial, cmdPos := 0 }
  return result
end ProbeParser

unsafe def main (args : List String) : IO UInt32 := do
  initSearchPath (← findSysroot)
  enableInitializersExecution
  let moduleName := (args.headD "Mathlib").toName
  let env ← importModules #[{module := moduleName}] {} (leakEnv := true) (loadExts := true)
  for owner in #["Mathlib.Order.Basic", "Mathlib.Tactic.NormNum.Basic", "Mathlib.AlgebraicGeometry.AffineTransitionLimit", "Mathlib.Order.Interval.Set.Basic", "Mathlib.Algebra.Quaternion", "Mathlib.Topology.Separation.Basic", "Mathlib.ModelTheory.Syntax"] do
    let path := System.FilePath.mk ((owner.replace "." "/") ++ ".lean")
    let source ← IO.FS.readFile path
    IO.println <| (Json.mkObj [("module", toJson owner), ("parsed", ← ProbeParser.measure env path.toString source)]).compress
  return 0
