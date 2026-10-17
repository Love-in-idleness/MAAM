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

unsafe def main (args : List String) : IO UInt32 := do
  initSearchPath (← findSysroot)
  enableInitializersExecution
  let moduleName := (args.headD "Mathlib").toName
  IO.eprintln s!"phase=import_start; module={moduleName}"
  let start ← IO.monoNanosNow
  let env ← importModules #[{module := moduleName}] {} (leakEnv := true) (loadExts := true)
  let stop ← IO.monoNanosNow
  IO.println <| (Json.mkObj [("phase", toJson "import_complete"),
    ("import_ms", toJson ((stop-start) / 1000000)),
    ("modules", toJson env.header.moduleNames.size)]).compress
  for owner in #["Mathlib.Order.Basic", "Mathlib.Tactic.NormNum.Basic", "Mathlib.AlgebraicGeometry.AffineTransitionLimit", "Mathlib.Order.Interval.Set.Basic", "Mathlib.Algebra.Quaternion", "Mathlib.Topology.Separation.Basic", "Mathlib.ModelTheory.Syntax"] do
    let path := System.FilePath.mk ((owner.replace "." "/") ++ ".lean")
    let source ← IO.FS.readFile path
    let tokens := ProbeLexer.lexSource env path.toString source
    IO.println <| (Json.mkObj [("module", toJson owner),
      ("error", toJson tokens.lexicalError), ("tokens", toJson tokens.starts.size)]).compress
  return 0
