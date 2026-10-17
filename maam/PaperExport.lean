/- Fixed-snapshot, streaming replication export. No unsafe-recursion cutoffs.
   const/Sort traversal follows ABFM §3.1; source tokens use Lean's own lexer.
   Whole declaration ranges are measured, including the declaration header.
   Lexical failure and absent/shared source ranges remain explicit missing data. -/
import Lean

open Lean
set_option maxRecDepth 1000000
set_option maxHeartbeats 0

namespace MAAMPaper

abbrev Counts := Std.HashMap Name Nat
def sortName : Name := Name.mkSimple "@Sort"
def bump (a : Counts) (n : Name) : Counts := a.insert n (a.getD n 0 + 1)
partial def collect (e : Expr) (a : Counts := {}) : Counts :=
  match e with
  | .const n _ => bump a n
  | .sort _ => bump a sortName
  | .app f x => collect x (collect f a)
  | .lam _ t b _ | .forallE _ t b _ => collect b (collect t a)
  | .letE _ t v b _ => collect b (collect v (collect t a))
  | .mdata _ x | .proj _ _ x => collect x a
  | _ => a

def refsJson (a : Counts) : Json :=
  Json.mkObj (a.toList.map fun (n, k) => (n.toString, toJson k))

def moduleOf (env : Environment) (n : Name) : String :=
  match env.getModuleIdxFor? n with
  | none => ""
  | some i => env.header.moduleNames[i.toNat]!.toString

def inScope (env : Environment) (scope : String) (n : Name) : Bool :=
  let m := moduleOf env n
  m == scope || m.startsWith (scope ++ ".")

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
      return { map := ctx.fileMap, starts := #[], lexicalError := some (toString err) }
    if next.pos <= pos then
      return { map := ctx.fileMap, starts := #[], lexicalError := some "lexer made no progress" }
    starts := starts.push pos.byteIdx
    state := next
  return { map := ctx.fileMap, starts, lexicalError := none }

def lowerBound (a : Array Nat) (value : Nat) : Nat := Id.run do
  let mut low := 0
  let mut high := a.size
  while low < high do
    let mid := (low + high) / 2
    if a[mid]! < value then low := mid + 1 else high := mid
  return low

def checkLexer (env : Environment) : IO Unit := do
  let examples : List (String × Nat) := [
    ("theorem isOpenMap_proj : IsOpenMap Z.proj := Z.toFiberBundleCore.isOpenMap_proj", 7),
    ("theorem integrable : Integrable f μ := f.continuous.integrable_of_hasCompactSupport f.hasCompactSupport", 9),
    ("theorem infinitesimal_zero : Infinitesimal 0 := isSt_refl_real 0", 8),
    ("/- outer /- nested -/ -/ /-- docs -/ theorem tiny : P := Q -- trailing", 6),
    ("def text : String := \"a b /- c -/\"", 6)]
  for (text, expected) in examples do
    let source := lexSource env "lexer-check" text
    if source.lexicalError.isSome || source.starts.size != expected then
      throw <| IO.userError s!"Lean lexer check failed: expected {expected}, got {source.starts.size}: {text}"

def sourceData (env : Environment) (name : Name) (source : Source) : Json := Id.run do
  if let some err := source.lexicalError then
    return Json.mkObj [("status", toJson "lexical_error"), ("error", toJson err)]
  let range := declRangeExt.find? (level := .exported) env name <|>
    declRangeExt.find? (level := .server) env name
  let some range := range | return Json.mkObj [("status", toJson "no_declaration_range")]
  let startPos := source.map.ofPosition range.range.pos
  let stopPos := source.map.ofPosition range.range.endPos
  let selectedStart := source.map.ofPosition range.selectionRange.pos
  let selectedEnd := source.map.ofPosition range.selectionRange.endPos
  let selected := source.map.source.extract selectedStart selectedEnd
  let userName := (privateToUserName name.eraseMacroScopes).toString
  let named := selected == userName || userName.endsWith ("." ++ selected)
  let count := lowerBound source.starts stopPos.byteIdx - lowerBound source.starts startPos.byteIdx
  return Json.mkObj [
    ("status", toJson (if named && !selected.isEmpty then "named_source" else "shared_or_generated_source")),
    ("tokens", toJson count), ("selected_name", toJson selected),
    ("start_line", toJson range.range.pos.line), ("end_line", toJson range.range.endPos.line),
    ("start_byte", toJson startPos.byteIdx), ("end_byte", toJson stopPos.byteIdx)]

def kindOf (info : ConstantInfo) : String :=
  match info with
  | .thmInfo _ => "theorem"
  | .axiomInfo _ => "axiom"
  | _ => "definition"

def exportAll (env : Environment) (mod scope sourceRoot output revision : String) : IO Unit := do
  let roots := env.constants.toList.filterMap fun (n, _) => if inScope env scope n then some n else none
  if roots.isEmpty then throw <| IO.userError "empty module scope"
  let handle ← IO.FS.Handle.mk output .write
  handle.putStrLn <| (Json.mkObj [
    ("record", toJson "metadata"), ("schema_version", toJson (1 : Nat)),
    ("module", toJson mod), ("scope", toJson scope), ("revision", toJson revision),
    ("lean_version", toJson Lean.versionString),
    ("primitive_policy", toJson "Sort and out-of-scope declarations only; unsafe definitions retained"),
    ("token_policy", toJson "Lean tokenFn on declaration ranges; all comments excluded; named/shared source reported separately"),
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
    let moduleName := moduleOf env name
    let primitive := !(inScope env scope name)
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
          sources := sources.insert moduleName (lexSource env path.toString text)
        else
          sources := sources.insert moduleName { map := FileMap.ofString "", starts := #[], lexicalError := some "source_file_missing" }
      source := sourceData env name (sources[moduleName]!)
    handle.putStrLn <| (Json.mkObj [
      ("record", toJson "node"), ("name", toJson name.toString),
      ("kind", toJson (if primitive then "primitive" else kindOf info)),
      ("module", toJson moduleName), ("unsafe", toJson info.isUnsafe),
      ("signature", refsJson sig), ("body", body.map refsJson |>.getD Json.null),
      ("source", source)]).compress
    done := done + 1
    if done % 25000 == 0 then IO.eprintln s!"Exported {done} declarations"
  handle.flush
  IO.eprintln s!"Finished: {seen.size} vertices; {sources.size} source modules"

end MAAMPaper

def main (args : List String) : IO UInt32 := do
  let [mod, scope, sourceRoot, output, revision] := args
    | throw <| IO.userError "usage: PaperExport.lean MODULE MODULE_PREFIX SOURCE_ROOT OUTPUT_JSONL REVISION"
  initSearchPath (← findSysroot)
  let env ← importModules #[{ module := mod.toName }] {} (loadExts := true)
  MAAMPaper.checkLexer env
  MAAMPaper.exportAll env mod scope sourceRoot output revision
  return 0
