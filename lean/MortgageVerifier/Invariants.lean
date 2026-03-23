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
-- NJ Regulatory Invariants (Waves 2–4)
-- ---------------------------------------------------------------------------

-- Wave 2 — NJ HOSA / Licensed Lenders

/-- N.J.S.A. 17:11C-28(a)(1): discount points on approval may not exceed 3.0. -/
def discountPointsCap (decision : RoutingDecision) (app : MortgageApplication)
    : Option String :=
  if decision.outcome == RoutingOutcome.approve
      && app.loan.discountPointsPct > 3.0 then
    some s!"Discount points {app.loan.discountPointsPct} exceed 3-point cap on \
approval (N.J.S.A. 17:11C-28(a)(1); decision {decision.decisionId})"
  else none

/-- N.J.S.A. 17:11C-28(c): late charge on approval may not exceed 5% of the payment. -/
def lateChargeCap (decision : RoutingDecision) (app : MortgageApplication)
    : Option String :=
  if decision.outcome == RoutingOutcome.approve
      && app.loan.lateChargePct > 0.05 then
    some s!"Late charge rate {app.loan.lateChargePct} exceeds 5% cap on approval \
(N.J.S.A. 17:11C-28(c); decision {decision.decisionId})"
  else none

/-- C.46:10B-24 (NJ HOSA): a high-cost home loan (principal $40k–$617,603, fees > 5%)
    must not receive direct algorithmic approval — it requires underwriter escalation.
    Loans above the 2025 HOSA ceiling ($617,603, DOBI Blt 25-02) are exempt. -/
def highCostLoanMustEscalate (decision : RoutingDecision) (app : MortgageApplication)
    : Option String :=
  if decision.outcome == RoutingOutcome.approve
      && isHighCostHomeLoan app then
    some s!"High-cost home loan (fees {app.loan.totalPointsAndFeesPct} > 5% on \
principal ${app.loan.principalUsd} within HOSA range) requires underwriter review \
before approval (C.46:10B-24; decision {decision.decisionId})"
  else none

/-- N.J.A.C. 3:25-1.1: loans > $40,000 with fees 4–5% qualify as "covered home loans"
    and require additional disclosures; direct approval is non-compliant. -/
def coveredHomeLoanFeeCheck (decision : RoutingDecision) (app : MortgageApplication)
    : Option String :=
  if decision.outcome == RoutingOutcome.approve
      && isCoveredHomeLoan app then
    some s!"Loan fees {app.loan.totalPointsAndFeesPct} exceed 4% threshold — \
classifies as covered home loan (N.J.A.C. 3:25-1.1); requires additional \
disclosures before approval (decision {decision.decisionId})"
  else none

/-- C.46:10B-26(a)(6) + P.L. 2025 c.56: high-cost home loans may not carry a
    prepayment penalty beyond 36 months. -/
def prepaymentPenaltyOnHighCost (decision : RoutingDecision) (app : MortgageApplication)
    : Option String :=
  if isHighCostHomeLoan app
      && app.loan.prepaymentPenaltyMonths > 36 then
    some s!"High-cost home loan carries prepayment penalty of \
{app.loan.prepaymentPenaltyMonths} months, exceeding the 36-month statutory cap \
(C.46:10B-26(a)(6); decision {decision.decisionId})"
  else none

/-- C.46:10B-26 (NJ HOSA): a high-cost home loan may not finance more than 2% of
    the loan amount in points into the loan balance. -/
def financedPointsOnHighCost (decision : RoutingDecision) (app : MortgageApplication)
    : Option String :=
  if decision.outcome == RoutingOutcome.approve
      && isHighCostHomeLoan app
      && app.loan.financedPointsUsd > app.loan.principalUsd * 0.02 then
    some s!"High-cost home loan finances ${app.loan.financedPointsUsd} in points, \
exceeding the 2%-of-principal cap (C.46:10B-26; decision {decision.decisionId})"
  else none

-- Wave 3 — Practitioner proxies

/-- N.J.A.C. 3:1-16.2 / CFPB ATR (12 CFR 1026.43(c)): an unemployed applicant
    cannot receive direct algorithmic approval; human underwriter sign-off required. -/
def unemployedApplicantRequiresEscalation
    (decision : RoutingDecision) (app : MortgageApplication)
    : Option String :=
  if decision.outcome == RoutingOutcome.approve
      && app.applicant.employmentStatus == EmploymentStatus.unemployed then
    some s!"Unemployed applicant cannot receive direct algorithmic approval; \
human underwriter sign-off required (N.J.A.C. 3:1-16.2 ATR principle; \
decision {decision.decisionId})"
  else none

/-- FHFA 2025: a JUMBO-labelled loan whose principal does not exceed the $806,500
    conforming limit carries an incorrect loan type label. -/
def jumboConformingLimitCheck (decision : RoutingDecision) (app : MortgageApplication)
    : Option String :=
  if decision.outcome == RoutingOutcome.approve
      && app.loan.loanType == LoanType.jumbo
      && app.loan.principalUsd <= conformingLoanLimit then
    some s!"JUMBO-labelled loan has principal ${app.loan.principalUsd} which does \
not exceed the FHFA 2025 conforming limit ${conformingLoanLimit}; loan type label \
is incorrect (FHFA 2025 CLL; decision {decision.decisionId})"
  else none

-- Wave 4 — Federal QM / CFPB overlays

/-- 12 CFR 1026.43(e)(3) (2025): for loans ≥ $134,841, total points & fees > 3%
    disqualifies the loan from QM safe harbour and requires escalation. -/
def qmPointsAndFeesCap (decision : RoutingDecision) (app : MortgageApplication)
    : Option String :=
  if decision.outcome == RoutingOutcome.approve
      && app.loan.principalUsd >= 134841.0
      && app.loan.totalPointsAndFeesPct > 0.03 then
    some s!"Loan fees {app.loan.totalPointsAndFeesPct} exceed the 3% QM points-and-fees \
cap for loans ≥ $134,841; loan is non-QM and requires escalation \
(12 CFR 1026.43(e)(3), 2025; decision {decision.decisionId})"
  else none

/-- 12 CFR 1026.43(e)(2)(vi) (2025): for first-lien loans ≥ $134,841, if
    APR − note rate ≥ 0.0225 (225 bps) the loan is non-QM. -/
def qmAprSpreadCheck (decision : RoutingDecision) (app : MortgageApplication)
    : Option String :=
  match app.loan.requestedRatePct with
  | none => none  -- rate not specified; cannot evaluate
  | some ratePct =>
    if decision.outcome == RoutingOutcome.approve
        && app.loan.principalUsd >= 134841.0
        && app.loan.aprPct - ratePct >= 0.0225 then
      some s!"APR spread {app.loan.aprPct - ratePct} ≥ 0.0225 on loan ≥ $134,841 \
indicates non-QM status; escalate for ATR review \
(12 CFR 1026.43(e)(2)(vi), 2025; decision {decision.decisionId})"
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
  [ -- Existing: DTI caps
    dtiCapConventional, dtiCapFHA, dtiCapVA, dtiCapJumbo
    -- Existing: LTV caps
  , ltvCapConventional, ltvCapFHA, ltvCapJumbo
    -- Existing: Credit score floors
  , creditFloorConventional, creditFloorFHA, creditFloorVA, creditFloorJumbo
    -- Existing: Escalation completeness
  , escalationRequiresReason
    -- Wave 2: NJ HOSA / Licensed Lenders
  , discountPointsCap             -- N.J.S.A. 17:11C-28(a)(1)
  , lateChargeCap                 -- N.J.S.A. 17:11C-28(c)
  , highCostLoanMustEscalate      -- C.46:10B-24  (5% threshold, 2025 HOSA ceiling)
  , coveredHomeLoanFeeCheck       -- N.J.A.C. 3:25-1.1  (4% intermediate tier)
  , prepaymentPenaltyOnHighCost   -- C.46:10B-26(a)(6) + P.L. 2025 c.56
  , financedPointsOnHighCost      -- C.46:10B-26  (2% cap)
    -- Wave 3: Practitioner proxies
  , unemployedApplicantRequiresEscalation  -- N.J.A.C. 3:1-16.2 ATR proxy
  , jumboConformingLimitCheck              -- FHFA 2025 baseline $806,500
    -- Wave 4: Federal QM overlays
  , qmPointsAndFeesCap            -- 12 CFR 1026.43(e)(3)  (2025: 3% / $134,841)
  , qmAprSpreadCheck              -- 12 CFR 1026.43(e)(2)(vi)  (2025: ≥225 bps)
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
