/- Discover the types, dependencies and source spans of named outer `have` tactics. -/
import Lean

open Lean Meta

namespace MAAMRefactor

structure Input where
  theoremName : String
  termPath : String
  deriving FromJson

structure Config where
  entry : String
  proofs : Array Input
  deriving FromJson

structure Span where
  name : Name
  start : Nat
  stop : Nat
  afterName : Nat
  deriving Inhabited

def haveSpan (tactic : Syntax) : Option Span := do
  guard (tactic.getKind == ``Parser.Tactic.tacticHave__)
  let decl := tactic[2][0]
  guard (decl.getKind == ``Parser.Term.letIdDecl)
  let name := decl[0][0]
  guard name.isIdent
  guard (!decl[2].getArgs.isEmpty)
  return {
    name := name.getId
    start := (← tactic.getPos?).byteIdx
    stop := (← tactic.getTailPos?).byteIdx
    afterName := (← name.getTailPos?).byteIdx
  }

def spans (stx : Syntax) : Array Span :=
  if stx.getKind == ``Parser.Term.byTactic &&
      stx[1][0].getKind == ``Parser.Tactic.tacticSeq1Indented then
    stx[1][0][0].getArgs.filterMap haveSpan
  else #[]

-- Keep constants and universe levels, but suppress binder names and elaborator annotations.
partial def normalize : Expr → Expr
  | .lam _ t b _ => .lam .anonymous (normalize t) (normalize b) .default
  | .forallE _ t b _ => .forallE .anonymous (normalize t) (normalize b) .default
  | .letE _ t v b _ => .letE .anonymous (normalize t) (normalize v) (normalize b) false
  | .mdata _ b => normalize b
  | .proj n i b => .proj n i (normalize b)
  | .app f x => .app (normalize f) (normalize x)
  | other => other

def key (vars : Array Expr) (e : Expr) : String :=
  (repr (normalize (e.abstract vars))).pretty

def closure (locals : Array LocalDecl) (refs : CollectFVars.State) : Array LocalDecl := Id.run do
  let mut refs := refs
  let mut result := #[]
  for decl in locals.reverse do
    if refs.fvarSet.contains decl.fvarId then
      result := result.push decl
      refs := collectFVars refs decl.type
  return result.reverse

def references (id : FVarId) (e : Expr) : Bool :=
  (collectFVars {} e).fvarSet.contains id

def site (locals later : Array LocalDecl) (decl : LocalDecl) (span : Span)
    (body : Expr) : MetaM (Option Json) := do
  let some value := decl.value? | return none
  if !(← isProp decl.type) then return none
  let support := closure locals (collectFVars {} decl.type)
  let vars := support.map (·.toExpr)
  let signature := (support.map fun d => key vars d.type).push (key vars decl.type)
  let parameters := closure locals (collectFVars (collectFVars {} decl.type) value)
  -- A parameter whose type needs another premise cannot be matched by this finite policy.
  let mut binders := #[]
  let mut eligible := true
  for param in parameters do
    let index := vars.idxOf? param.toExpr
    let abstracted := param.type.abstract vars
    if index.isNone && abstracted.hasFVar then eligible := false
    binders := binders.push <| Json.mkObj [
      ("name", toJson param.userName.toString), ("type", toJson (← ppExpr param.type).pretty),
      ("index", toJson index), ("key", toJson (key vars param.type))]
  let options := locals.filter fun d => !(d.type.abstract vars).hasFVar
  let context := options.map fun d => Json.mkObj [
    ("name", toJson d.userName.toString), ("key", toJson (key vars d.type))]
  let refs := references decl.fvarId
  let users := later.filter fun d => refs d.type || d.value?.any refs
  let inBody := refs body
  return some <| Json.mkObj [
    ("name", toJson span.name.toString), ("start", toJson span.start),
    ("stop", toJson span.stop), ("after_name", toJson span.afterName),
    ("live", toJson (inBody || !users.isEmpty)), ("shape", toJson signature),
    ("in_body", toJson inBody), ("users", toJson (users.map (·.userName.toString))),
    ("type", toJson (← ppExpr decl.type).pretty), ("term", toJson (← ppExpr value).pretty),
    ("support", toJson (support.map (·.userName.toString))), ("context", toJson context),
    ("binders", toJson binders), ("eligible", toJson eligible)]

def inspect (env : Environment) (input : Input) : IO (Array Json) := do
  let stx ← IO.ofExcept <| Parser.runParserCategory env `term (← IO.FS.readFile input.termPath)
  let ranges := spans stx
  let some info := env.find? input.theoremName.toName
    | throw <| IO.userError s!"missing theorem {input.theoremName}"
  let some value := info.value? (allowOpaque := true) | throw <| IO.userError "missing proof value"
  let action : MetaM (Array Json) :=
    lambdaLetTelescope value (preserveNondepLet := false) fun xs body => do
      let declarations ← xs.mapM fun x => x.fvarId!.getDecl
      let mut result := #[]
      for i in [:declarations.size] do
        let decl := declarations[i]!
        let found := ranges.filter (·.name == decl.userName)
        if found.size != 1 || (declarations.filter (·.userName == decl.userName)).size != 1 then continue
        if let some row ← site (declarations.extract 0 i) (declarations.extract (i+1) declarations.size)
            decl found[0]! body then
          result := result.push row
      return result
  let (rows, _, _) ← action.toIO {fileName := input.termPath, fileMap := default} {env}
  return rows

end MAAMRefactor

unsafe def main (args : List String) : IO UInt32 := do
  let [config, output] := args | throw <| IO.userError "usage: RefactorSites.lean INPUT OUTPUT"
  let cfg : MAAMRefactor.Config ← IO.ofExcept <| (Json.parse (← IO.FS.readFile config)).bind fromJson?
  initSearchPath (← findSysroot)
  enableInitializersExecution
  let env ← importModules #[{module := cfg.entry.toName}] {} (leakEnv := true) (loadExts := true)
  let rows ← cfg.proofs.mapM fun p => MAAMRefactor.inspect env p
  IO.FS.writeFile output (toJson rows).compress
  return 0
