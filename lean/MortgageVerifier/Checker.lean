import MortgageVerifier.Types
import MortgageVerifier.Invariants

/-!
# Checker.lean

Runs all invariants against a parsed DecisionRecord and produces
a structured `CheckResult` that Main.lean serialises to JSON.
-/

namespace MortgageVerifier.Checker

open Lean MortgageVerifier.Invariants

-- ---------------------------------------------------------------------------
-- Result type
-- ---------------------------------------------------------------------------

structure Violation where
  invariantName : String
  description   : String
  severity      : String  -- "ERROR" for all violations currently

structure CheckResult where
  passed      : Bool
  recordId    : String
  violations  : List Violation
  leanVersion : String

-- ---------------------------------------------------------------------------
-- Violation name extraction from message prefix
-- ---------------------------------------------------------------------------

private def violationName (msg : String) : String :=
  if msg.startsWith "DTI" then
    if msg.contains "CONVENTIONAL" then "dtiCapConventional"
    else if msg.contains "FHA"     then "dtiCapFHA"
    else if msg.contains "VA"      then "dtiCapVA"
    else if msg.contains "JUMBO"   then "dtiCapJumbo"
    else "dtiCap"
  else if msg.startsWith "LTV" then
    if msg.contains "CONVENTIONAL" then "ltvCapConventional"
    else if msg.contains "FHA"     then "ltvCapFHA"
    else if msg.contains "JUMBO"   then "ltvCapJumbo"
    else "ltvCap"
  else if msg.startsWith "Credit" then
    if msg.contains "CONVENTIONAL" then "creditFloorConventional"
    else if msg.contains "FHA"     then "creditFloorFHA"
    else if msg.contains "VA"      then "creditFloorVA"
    else if msg.contains "JUMBO"   then "creditFloorJumbo"
    else "creditFloor"
  else if msg.startsWith "ESCALATE" then "escalationRequiresReason"
  else if msg.startsWith "final_outcome" || msg.startsWith "Record has no"
                                    then "finalOutcomeConsistency"
  else "unknown_invariant"

-- ---------------------------------------------------------------------------
-- Top-level check
-- ---------------------------------------------------------------------------

def check (dr : DecisionRecord) : CheckResult :=
  let messages   := checkRecord dr
  let violations := messages.map fun msg =>
    { invariantName := violationName msg, description := msg, severity := "ERROR" }
  { passed      := violations.isEmpty
  , recordId    := dr.recordId
  , violations  := violations
  , leanVersion := Lean.versionString
  }

-- ---------------------------------------------------------------------------
-- JSON serialisation of CheckResult
-- ---------------------------------------------------------------------------

private def escapeJson (s : String) : String :=
  s.foldl (fun acc c =>
    match c with
    | '"'  => acc ++ "\\\""
    | '\\' => acc ++ "\\\\"
    | '\n' => acc ++ "\\n"
    | '\r' => acc ++ "\\r"
    | '\t' => acc ++ "\\t"
    | _    => acc ++ c.toString
  ) ""

private def jsonStr (s : String) : String :=
  "\"" ++ escapeJson s ++ "\""

private def violationToJson (v : Violation) : String :=
  "{" ++
  "\"invariant_name\":" ++ jsonStr v.invariantName ++ "," ++
  "\"description\":"    ++ jsonStr v.description   ++ "," ++
  "\"severity\":"       ++ jsonStr v.severity       ++
  "}"

def resultToJson (r : CheckResult) : String :=
  let passedStr := if r.passed then "true" else "false"
  let vsArr     := "[" ++ String.intercalate "," (r.violations.map violationToJson) ++ "]"
  "{" ++
  "\"passed\":"       ++ passedStr         ++ "," ++
  "\"record_id\":"    ++ jsonStr r.recordId ++ "," ++
  "\"violations\":"   ++ vsArr             ++ "," ++
  "\"lean_version\":" ++ jsonStr r.leanVersion ++
  "}"

end MortgageVerifier.Checker
