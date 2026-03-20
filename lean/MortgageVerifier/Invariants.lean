import MortgageVerifier.Types

/-!
# Invariants.lean

Formal routing invariants that every valid DecisionRecord must satisfy.

Each invariant is a function `RoutingDecision → MortgageApplication → Option String`
returning `none` if the invariant holds and `some errorMessage` if it is violated.
This makes the checker compositional: collect all `some` results as violations.

Thresholds must be kept in sync with:
  - src/verified_mortgage_agent/domain/validators.py
-/

namespace MortgageVerifier.Invariants

-- ---------------------------------------------------------------------------
-- DTI caps (debt-to-income ratio)
-- ---------------------------------------------------------------------------

/-- Conventional loans: approve only if DTI < 0.43 -/
def dtiCapConventional (decision : RoutingDecision) (app : MortgageApplication)
    : Option String :=
  if decision.outcome == RoutingOutcome.approve
      && app.loan.loanType == LoanType.conventional
      && debtToIncomeRatio app >= 0.43 then
    some s!"DTI {debtToIncomeRatio app} exceeds cap 0.43 for CONVENTIONAL approval \
(decision {decision.decisionId})"
  else none

/-- FHA loans: approve only if DTI < 0.50 -/
def dtiCapFHA (decision : RoutingDecision) (app : MortgageApplication)
    : Option String :=
  if decision.outcome == RoutingOutcome.approve
      && app.loan.loanType == LoanType.fha
      && debtToIncomeRatio app >= 0.50 then
    some s!"DTI {debtToIncomeRatio app} exceeds cap 0.50 for FHA approval \
(decision {decision.decisionId})"
  else none

/-- VA loans: approve only if DTI < 0.41 -/
def dtiCapVA (decision : RoutingDecision) (app : MortgageApplication)
    : Option String :=
  if decision.outcome == RoutingOutcome.approve
      && app.loan.loanType == LoanType.va
      && debtToIncomeRatio app >= 0.41 then
    some s!"DTI {debtToIncomeRatio app} exceeds cap 0.41 for VA approval \
(decision {decision.decisionId})"
  else none

/-- Jumbo loans: approve only if DTI < 0.38 -/
def dtiCapJumbo (decision : RoutingDecision) (app : MortgageApplication)
    : Option String :=
  if decision.outcome == RoutingOutcome.approve
      && app.loan.loanType == LoanType.jumbo
      && debtToIncomeRatio app >= 0.38 then
    some s!"DTI {debtToIncomeRatio app} exceeds cap 0.38 for JUMBO approval \
(decision {decision.decisionId})"
  else none

-- ---------------------------------------------------------------------------
-- LTV caps (loan-to-value ratio)
-- ---------------------------------------------------------------------------

/-- Conventional: approve only if LTV ≤ 0.97 -/
def ltvCapConventional (decision : RoutingDecision) (app : MortgageApplication)
    : Option String :=
  if decision.outcome == RoutingOutcome.approve
      && app.loan.loanType == LoanType.conventional
      && loanToValueRatio app > 0.97 then
    some s!"LTV {loanToValueRatio app} exceeds cap 0.97 for CONVENTIONAL approval \
(decision {decision.decisionId})"
  else none

/-- FHA: approve only if LTV ≤ 0.965 (3.5% minimum down payment) -/
def ltvCapFHA (decision : RoutingDecision) (app : MortgageApplication)
    : Option String :=
  if decision.outcome == RoutingOutcome.approve
      && app.loan.loanType == LoanType.fha
      && loanToValueRatio app > 0.965 then
    some s!"LTV {loanToValueRatio app} exceeds cap 0.965 for FHA approval \
(decision {decision.decisionId})"
  else none

/-- Jumbo: approve only if LTV ≤ 0.80 -/
def ltvCapJumbo (decision : RoutingDecision) (app : MortgageApplication)
    : Option String :=
  if decision.outcome == RoutingOutcome.approve
      && app.loan.loanType == LoanType.jumbo
      && loanToValueRatio app > 0.80 then
    some s!"LTV {loanToValueRatio app} exceeds cap 0.80 for JUMBO approval \
(decision {decision.decisionId})"
  else none

-- ---------------------------------------------------------------------------
-- Credit score floors
-- ---------------------------------------------------------------------------

/-- Conventional: approve only if credit score ≥ 620 -/
def creditFloorConventional (decision : RoutingDecision) (app : MortgageApplication)
    : Option String :=
  if decision.outcome == RoutingOutcome.approve
      && app.loan.loanType == LoanType.conventional
      && app.applicant.creditScore < 620 then
    some s!"Credit score {app.applicant.creditScore} below minimum 620 for CONVENTIONAL \
(decision {decision.decisionId})"
  else none

/-- FHA: approve only if credit score ≥ 580 -/
def creditFloorFHA (decision : RoutingDecision) (app : MortgageApplication)
    : Option String :=
  if decision.outcome == RoutingOutcome.approve
      && app.loan.loanType == LoanType.fha
      && app.applicant.creditScore < 580 then
    some s!"Credit score {app.applicant.creditScore} below minimum 580 for FHA \
(decision {decision.decisionId})"
  else none

/-- VA: approve only if credit score ≥ 580 -/
def creditFloorVA (decision : RoutingDecision) (app : MortgageApplication)
    : Option String :=
  if decision.outcome == RoutingOutcome.approve
      && app.loan.loanType == LoanType.va
      && app.applicant.creditScore < 580 then
    some s!"Credit score {app.applicant.creditScore} below minimum 580 for VA \
(decision {decision.decisionId})"
  else none

/-- Jumbo: approve only if credit score ≥ 700 -/
def creditFloorJumbo (decision : RoutingDecision) (app : MortgageApplication)
    : Option String :=
  if decision.outcome == RoutingOutcome.approve
      && app.loan.loanType == LoanType.jumbo
      && app.applicant.creditScore < 700 then
    some s!"Credit score {app.applicant.creditScore} below minimum 700 for JUMBO \
(decision {decision.decisionId})"
  else none

-- ---------------------------------------------------------------------------
-- Escalation completeness
-- ---------------------------------------------------------------------------

/-- Any escalation decision must include a non-empty escalation_reason -/
def escalationRequiresReason (decision : RoutingDecision) (_ : MortgageApplication)
    : Option String :=
  if decision.outcome == RoutingOutcome.escalateToUnderwriter then
    match decision.escalationReason with
    | none =>
      some s!"ESCALATE_TO_UNDERWRITER decision {decision.decisionId} \
has no escalation_reason"
    | some reason =>
      if reason.trim.isEmpty then
        some s!"ESCALATE_TO_UNDERWRITER decision {decision.decisionId} \
has empty escalation_reason"
      else none
  else none

-- ---------------------------------------------------------------------------
-- Record-level consistency
-- ---------------------------------------------------------------------------

/-- The record's final_outcome must match the last decision's outcome -/
def finalOutcomeConsistency (record : DecisionRecord) : Option String :=
  match record.decisions.getLast? with
  | none =>
    some "Record has no decisions; final_outcome cannot be verified"
  | some lastDecision =>
    if lastDecision.outcome != record.finalOutcome then
      some s!"final_outcome {repr record.finalOutcome} does not match \
last decision outcome {repr lastDecision.outcome} (decision {lastDecision.decisionId})"
    else none

-- ---------------------------------------------------------------------------
-- Aggregate: all per-decision invariants
-- ---------------------------------------------------------------------------

/-- All invariants that apply to a single RoutingDecision in context. -/
def decisionInvariants : List (RoutingDecision → MortgageApplication → Option String) :=
  [ dtiCapConventional
  , dtiCapFHA
  , dtiCapVA
  , dtiCapJumbo
  , ltvCapConventional
  , ltvCapFHA
  , ltvCapJumbo
  , creditFloorConventional
  , creditFloorFHA
  , creditFloorVA
  , creditFloorJumbo
  , escalationRequiresReason
  ]

/-- Check all per-decision invariants and collect violation messages. -/
def checkDecision (decision : RoutingDecision) (app : MortgageApplication)
    : List String :=
  decisionInvariants.filterMap (fun inv => inv decision app)

/-- Check all invariants across the full record. Returns all violation messages. -/
def checkRecord (record : DecisionRecord) : List String :=
  let decisionViolations :=
    record.decisions.flatMap (fun d => checkDecision d record.application)
  let recordViolations :=
    [finalOutcomeConsistency record].filterMap id
  decisionViolations ++ recordViolations

end MortgageVerifier.Invariants
