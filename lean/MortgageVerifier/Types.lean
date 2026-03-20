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
  principalUsd      : Float
  termYears         : Nat
  loanType          : LoanType
  requestedRatePct  : Option Float
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

end MortgageVerifier
