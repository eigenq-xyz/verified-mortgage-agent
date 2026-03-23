/-!
# Types.lean

Lean mirrors of the Python `record/models.py` types.
Field names use camelCase to match standard Lean convention; the Parser
maps snake_case JSON keys to these names.

Keep in sync with:
  - src/verified_mortgage_agent/record/models.py
  - src/verified_mortgage_agent/domain/enums.py
  - schemas/decision_record.json  (SCHEMA_VERSION = "1.0.0")
-/

namespace MortgageVerifier

-- ---------------------------------------------------------------------------
-- Enumerations
-- ---------------------------------------------------------------------------

inductive RoutingOutcome where
  | approve
  | reject
  | requestDocuments
  | escalateToUnderwriter
  deriving Repr, BEq, DecidableEq

inductive LoanType where
  | conventional
  | fha
  | va
  | jumbo
  deriving Repr, BEq, DecidableEq

inductive EmploymentStatus where
  | employed
  | selfEmployed
  | retired
  | unemployed
  deriving Repr, BEq, DecidableEq

inductive PropertyType where
  | singleFamily
  | condo
  | multiFamily
  | commercial
  deriving Repr, BEq, DecidableEq

inductive DocumentType where
  | bankStatement
  | taxReturn
  | employmentVerification
  | appraisal
  | creditReport
  | payStub
  | governmentId
  deriving Repr, BEq, DecidableEq

-- ---------------------------------------------------------------------------
-- Domain sub-types
-- ---------------------------------------------------------------------------

structure Applicant where
  name                       : String
  annualIncomeUsd            : Float
  creditScore                : Nat
  employmentStatus           : EmploymentStatus
  debtObligationsMonthlyUsd  : Float
  deriving Repr

structure Property where
  address          : String
  appraisedValueUsd : Float
  propertyType     : PropertyType
  deriving Repr

structure LoanRequest where
  principalUsd            : Float
  termYears               : Nat
  loanType                : LoanType
  requestedRatePct        : Option Float
  -- NJ regulatory / federal compliance fields (default 0 when absent from JSON)
  discountPointsPct       : Float  -- discount points at origination
                                   -- cap ≤ 3.0  N.J.S.A. 17:11C-28(a)(1)
  totalPointsAndFeesPct   : Float  -- (points + fees) / principalUsd
                                   -- HOSA high-cost trigger > 5% on loans ≥ $40k  C.46:10B-24
                                   -- Covered home loan trigger > 4%  N.J.A.C. 3:25
                                   -- QM safe-harbour trigger > 3%  12 CFR 1026.43(e)(3)
  lateChargePct           : Float  -- late charge as fraction of payment in default
                                   -- cap ≤ 5%  N.J.S.A. 17:11C-28(c)
  prepaymentPenaltyMonths : Nat    -- prepayment penalty duration in months
                                   -- cap 36 months on high-cost loans  C.46:10B-26(a)(6)
  financedPointsUsd       : Float  -- dollar amount of points financed into the loan
                                   -- cap ≤ 2% of loan amount on high-cost  C.46:10B-26
  aprPct                  : Float  -- annual percentage rate as a decimal (e.g. 0.075)
                                   -- QM: first-lien non-QM if APR ≥ APOR + 0.0225
                                   -- 12 CFR 1026.43(e)(2)(vi) [threshold for 2025: $134,841+]
  deriving Repr

structure MortgageApplication where
  id                : String   -- UUID as string
  applicant         : Applicant
  property          : Property
  loan              : LoanRequest
  submittedAt       : String   -- ISO-8601 datetime as string
  providedDocuments : List DocumentType
  deriving Repr

-- ---------------------------------------------------------------------------
-- Decision record types
-- ---------------------------------------------------------------------------

structure ReasoningStep where
  stepIndex         : Nat
  description       : String
  inputsConsidered  : List String
  ruleCited         : Option String
  deriving Repr

structure RoutingDecision where
  decisionId         : String   -- UUID as string
  applicationId      : String
  agentName          : String
  outcome            : RoutingOutcome
  reasoningSteps     : List ReasoningStep
  confidenceScore    : Float
  documentsRequested : List DocumentType
  escalationReason   : Option String
  decidedAt          : String
  modelId            : String
  deriving Repr

structure DecisionRecord where
  recordId       : String
  schemaVersion  : String
  application    : MortgageApplication
  decisions      : List RoutingDecision
  routingSteps   : List ReasoningStep
  finalOutcome   : RoutingOutcome
  generatedAt    : String
  modelId        : String
  deriving Repr

-- ---------------------------------------------------------------------------
-- Derived financial ratios (computed from raw fields, not stored in JSON)
-- ---------------------------------------------------------------------------

def debtToIncomeRatio (app : MortgageApplication) : Float :=
  let monthlyIncome := app.applicant.annualIncomeUsd / 12.0
  if monthlyIncome == 0.0 then 999.0
  else app.applicant.debtObligationsMonthlyUsd / monthlyIncome

def loanToValueRatio (app : MortgageApplication) : Float :=
  let appraised := app.property.appraisedValueUsd
  if appraised == 0.0 then 999.0
  else app.loan.principalUsd / appraised

/-- NJ HOSA (C.46:10B-24): principal ≥ $40,000 AND fees > 5% → high-cost home loan.
    The 2025 HOSA applicability ceiling is $617,603 (DOBI Blt 25-02); loans above
    this amount are exempt from HOSA. -/
def isHighCostHomeLoan (app : MortgageApplication) : Bool :=
  app.loan.principalUsd >= 40000.0
    && app.loan.principalUsd <= 617603.0
    && app.loan.totalPointsAndFeesPct > 0.05

/-- N.J.A.C. 3:25: "covered home loan" — intermediate tier below high-cost. -/
def isCoveredHomeLoan (app : MortgageApplication) : Bool :=
  app.loan.principalUsd > 40000.0
    && app.loan.totalPointsAndFeesPct > 0.04
    && !isHighCostHomeLoan app

/-- FHFA 2025 conforming loan limit for NJ standard counties. -/
def conformingLoanLimit : Float := 806500.0

/-- FHFA 2025 high-cost NJ county limit (Bergen, Essex, Hudson, Middlesex,
    Monmouth, Morris, Ocean, Passaic, Somerset, Union, Hunterdon, Sussex). -/
def highCostCountyLimit : Float := 1209750.0

end MortgageVerifier
