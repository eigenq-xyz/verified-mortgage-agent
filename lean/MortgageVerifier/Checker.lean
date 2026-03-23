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

-- String.contains in Lean 4 core takes a Char, not a String.
-- Use splitOn to check for a substring: if sub is present, splitOn yields ≥ 2 parts.
private def strHas (s sub : String) : Bool :=
  (s.splitOn sub).length > 1

private def violationName (msg : String) : String :=
  if msg.startsWith "DTI" then
    if strHas msg "CONVENTIONAL" then "dtiCapConventional"
    else if strHas msg "FHA"     then "dtiCapFHA"
    else if strHas msg "VA"      then "dtiCapVA"
    else if strHas msg "JUMBO"   then "dtiCapJumbo"
    else "dtiCap"
  else if msg.startsWith "LTV" then
    if strHas msg "CONVENTIONAL" then "ltvCapConventional"
    else if strHas msg "FHA"     then "ltvCapFHA"
    else if strHas msg "JUMBO"   then "ltvCapJumbo"
    else "ltvCap"
  else if msg.startsWith "Credit" then
    if strHas msg "CONVENTIONAL" then "creditFloorConventional"
    else if strHas msg "FHA"     then "creditFloorFHA"
    else if strHas msg "VA"      then "creditFloorVA"
    else if strHas msg "JUMBO"   then "creditFloorJumbo"
    else "creditFloor"
  else if msg.startsWith "ESCALATE" then "escalationRequiresReason"
  else if msg.startsWith "final_outcome" || msg.startsWith "Record has no"
                                    then "finalOutcomeConsistency"
  -- NJ regulatory / federal QM invariants
  else if msg.startsWith "Discount points"   then "discountPointsCap"
  else if msg.startsWith "Late charge"       then "lateChargeCap"
  else if msg.startsWith "High-cost home loan" && strHas msg "underwriter review"
                                             then "highCostLoanMustEscalate"
  else if msg.startsWith "Loan fees" && strHas msg "covered home loan"
                                             then "coveredHomeLoanFeeCheck"
  else if msg.startsWith "High-cost home loan" && strHas msg "prepayment penalty"
                                             then "prepaymentPenaltyOnHighCost"
  else if msg.startsWith "High-cost home loan" && strHas msg "finances $"
                                             then "financedPointsOnHighCost"
  else if msg.startsWith "Unemployed"        then "unemployedApplicantRequiresEscalation"
  else if msg.startsWith "JUMBO-labelled"    then "jumboConformingLimitCheck"
  else if msg.startsWith "Loan fees" && strHas msg "QM points-and-fees"
                                             then "qmPointsAndFeesCap"
  else if msg.startsWith "APR spread"        then "qmAprSpreadCheck"
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
