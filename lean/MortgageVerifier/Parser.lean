import Lean.Data.Json
import MortgageVerifier.Types

/-!
# Parser.lean

JSON → Lean type deserialization using `Lean.Data.Json`.

`RBNode.find?` does not exist in Lean 4.14.0, so object field lookup is
implemented via `RBNode.foldl` over the key-value pairs.

Each `parse*` function returns `Except String T`, threading errors upward.
The top-level `parseDecisionRecord` is what `Main.lean` calls.
-/

namespace MortgageVerifier.Parser

open Lean

-- ---------------------------------------------------------------------------
-- Field access helpers
-- In Lean ≥ 4.26, Json.getObjVal? returns Except String Json directly.
-- For optional fields, Json.obj holds Std.TreeMap.Raw with get? : key → Option.
-- ---------------------------------------------------------------------------

-- Required field: error if absent
private def getField (j : Json) (key : String) : Except String Json :=
  j.getObjVal? key

-- Optional field lookup (present/null → none, string → some, wrong type → error)
private def optLookup (j : Json) (key : String) : Option Json :=
  match j with
  | .obj m => m.get? key
  | _      => none

private def getString (j : Json) (key : String) : Except String String := do
  match ← getField j key with
  | .str s => .ok s
  | v      => .error s!"field '{key}' expected string, got {v}"

-- Pydantic serialises Decimal as a JSON string (e.g. "120000"), so accept
-- both JSON numbers and numeric strings for monetary / percentage fields.
private def getFloat (j : Json) (key : String) : Except String Float := do
  match ← getField j key with
  | .num n => .ok n.toFloat
  | .str s =>
    -- Pydantic serialises Decimal as a quoted number: parse it back via Json
    match Lean.Json.parse s with
    | .ok (.num n) => .ok n.toFloat
    | _            => .error s!"field '{key}' string '{s}' is not a valid number"
  | v => .error s!"field '{key}' expected number or numeric string, got {v}"

private def getNat (j : Json) (key : String) : Except String Nat := do
  match ← getField j key with
  | .num n =>
    if n.exponent == 0 && n.mantissa >= 0 then
      .ok n.mantissa.toNat
    else
      .error s!"field '{key}' not a non-negative integer (mantissa={n.mantissa}, exp={n.exponent})"
  | .str s =>
    match s.toNat? with
    | some n => .ok n
    | none   => .error s!"field '{key}' string '{s}' is not a valid Nat"
  | v => .error s!"field '{key}' expected number or numeric string, got {v}"

private def getOptString (j : Json) (key : String) : Except String (Option String) :=
  match optLookup j key with
  | none | some .null => .ok none
  | some (.str s)     => .ok (some s)
  | some v            => .error s!"field '{key}' expected string or null, got {v}"

private def getOptFloat (j : Json) (key : String) : Except String (Option Float) :=
  match optLookup j key with
  | none | some .null => .ok none
  | some (.num n)     => .ok (some n.toFloat)
  | some (.str s) =>
    -- Pydantic serialises Decimal as a quoted number: parse it back via Json
    match Lean.Json.parse s with
    | .ok (.num n) => .ok (some n.toFloat)
    | _            => .error s!"field '{key}' string '{s}' is not a valid number"
  | some v => .error s!"field '{key}' expected number or null, got {v}"

-- Optional numeric fields that default to 0 when absent (used for NJ/QM regulatory fields)
private def getOptFloatDefault (j : Json) (key : String) : Except String Float := do
  match ← getOptFloat j key with
  | some v => .ok v
  | none   => .ok 0.0

private def getOptNatDefault (j : Json) (key : String) : Except String Nat :=
  match optLookup j key with
  | none | some .null => .ok 0
  | some (.num n) =>
    if n.exponent == 0 && n.mantissa >= 0 then .ok n.mantissa.toNat
    else .error s!"field '{key}' not a non-negative integer (mantissa={n.mantissa}, exp={n.exponent})"
  | some v => .error s!"field '{key}' expected number or null, got {v}"

private def getArray (j : Json) (key : String) : Except String (Array Json) := do
  match ← getField j key with
  | .arr a => .ok a
  | v      => .error s!"field '{key}' expected array, got {v}"

-- ---------------------------------------------------------------------------
-- Enum parsers
-- ---------------------------------------------------------------------------

private def parseRoutingOutcome (s : String) : Except String RoutingOutcome :=
  match s with
  | "APPROVE"                 => .ok .approve
  | "REJECT"                  => .ok .reject
  | "REQUEST_DOCUMENTS"       => .ok .requestDocuments
  | "ESCALATE_TO_UNDERWRITER" => .ok .escalateToUnderwriter
  | _                         => .error s!"unknown RoutingOutcome: '{s}'"

private def parseLoanType (s : String) : Except String LoanType :=
  match s with
  | "CONVENTIONAL" => .ok .conventional
  | "FHA"          => .ok .fha
  | "VA"           => .ok .va
  | "JUMBO"        => .ok .jumbo
  | _              => .error s!"unknown LoanType: '{s}'"

private def parseEmploymentStatus (s : String) : Except String EmploymentStatus :=
  match s with
  | "EMPLOYED"      => .ok .employed
  | "SELF_EMPLOYED" => .ok .selfEmployed
  | "RETIRED"       => .ok .retired
  | "UNEMPLOYED"    => .ok .unemployed
  | _               => .error s!"unknown EmploymentStatus: '{s}'"

private def parsePropertyType (s : String) : Except String PropertyType :=
  match s with
  | "SINGLE_FAMILY" => .ok .singleFamily
  | "CONDO"         => .ok .condo
  | "MULTI_FAMILY"  => .ok .multiFamily
  | "COMMERCIAL"    => .ok .commercial
  | _               => .error s!"unknown PropertyType: '{s}'"

private def parseDocumentType (s : String) : Except String DocumentType :=
  match s with
  | "BANK_STATEMENT"          => .ok .bankStatement
  | "TAX_RETURN"              => .ok .taxReturn
  | "EMPLOYMENT_VERIFICATION" => .ok .employmentVerification
  | "APPRAISAL"               => .ok .appraisal
  | "CREDIT_REPORT"           => .ok .creditReport
  | "PAY_STUB"                => .ok .payStub
  | "GOVERNMENT_ID"           => .ok .governmentId
  | _                         => .error s!"unknown DocumentType: '{s}'"

private def parseDocumentList (arr : Array Json) : Except String (List DocumentType) :=
  arr.toList.mapM fun item =>
    match item with
    | .str s => parseDocumentType s
    | _      => .error s!"document list item expected string, got {item}"

-- ---------------------------------------------------------------------------
-- Domain sub-type parsers
-- ---------------------------------------------------------------------------

private def parseApplicant (j : Json) : Except String Applicant := do
  return {
    name                      := ← getString j "name"
    annualIncomeUsd           := ← getFloat  j "annual_income_usd"
    creditScore               := ← getNat    j "credit_score"
    employmentStatus          := ← parseEmploymentStatus (← getString j "employment_status")
    debtObligationsMonthlyUsd := ← getFloat  j "debt_obligations_monthly_usd"
  }

private def parseProperty (j : Json) : Except String Property := do
  return {
    address          := ← getString j "address"
    appraisedValueUsd := ← getFloat j "appraised_value_usd"
    propertyType     := ← parsePropertyType (← getString j "property_type")
  }

private def parseLoanRequest (j : Json) : Except String LoanRequest := do
  return {
    principalUsd            := ← getFloat          j "principal_usd"
    termYears               := ← getNat             j "term_years"
    loanType                := ← parseLoanType (← getString j "loan_type")
    requestedRatePct        := ← getOptFloat        j "requested_rate_pct"
    -- NJ regulatory / federal compliance fields (default 0 when absent)
    discountPointsPct       := ← getOptFloatDefault j "discount_points_pct"
    totalPointsAndFeesPct   := ← getOptFloatDefault j "total_points_and_fees_pct"
    lateChargePct           := ← getOptFloatDefault j "late_charge_pct"
    prepaymentPenaltyMonths := ← getOptNatDefault   j "prepayment_penalty_months"
    financedPointsUsd       := ← getOptFloatDefault j "financed_points_usd"
    aprPct                  := ← getOptFloatDefault j "apr_pct"
  }

private def parseMortgageApplication (j : Json) : Except String MortgageApplication := do
  return {
    id                := ← getString j "id"
    applicant         := ← parseApplicant  (← getField j "applicant")
    property          := ← parseProperty   (← getField j "property")
    loan              := ← parseLoanRequest (← getField j "loan")
    submittedAt       := ← getString j "submitted_at"
    providedDocuments := ← parseDocumentList (← getArray j "provided_documents")
  }

-- ---------------------------------------------------------------------------
-- Trace type parsers
-- ---------------------------------------------------------------------------

private def parseReasoningStep (j : Json) : Except String ReasoningStep := do
  let inputs := (← getArray j "inputs_considered").toList.filterMap fun item =>
    match item with | .str s => some s | _ => none
  return {
    stepIndex        := ← getNat    j "step_index"
    description      := ← getString j "description"
    inputsConsidered := inputs
    ruleCited        := ← getOptString j "rule_cited"
  }

private def parseRoutingDecision (j : Json) : Except String RoutingDecision := do
  return {
    decisionId         := ← getString j "decision_id"
    applicationId      := ← getString j "application_id"
    agentName          := ← getString j "agent_name"
    outcome            := ← parseRoutingOutcome (← getString j "outcome")
    reasoningSteps     := ← (← getArray j "reasoning_steps").toList.mapM parseReasoningStep
    confidenceScore    := ← getFloat j "confidence_score"
    documentsRequested := ← parseDocumentList (← getArray j "documents_requested")
    escalationReason   := ← getOptString j "escalation_reason"
    decidedAt          := ← getString j "decided_at"
    modelId            := ← getString j "model_id"
  }

-- ---------------------------------------------------------------------------
-- Top-level entry point
-- ---------------------------------------------------------------------------

def parseDecisionRecord (j : Json) : Except String DecisionRecord := do
  return {
    recordId      := ← getString j "record_id"
    schemaVersion := ← getString j "schema_version"
    application   := ← parseMortgageApplication (← getField j "application")
    decisions     := ← (← getArray j "decisions").toList.mapM parseRoutingDecision
    routingSteps  := ← (← getArray j "routing_steps").toList.mapM parseReasoningStep
    finalOutcome  := ← parseRoutingOutcome (← getString j "final_outcome")
    generatedAt   := ← getString j "generated_at"
    modelId       := ← getString j "model_id"
  }

end MortgageVerifier.Parser
