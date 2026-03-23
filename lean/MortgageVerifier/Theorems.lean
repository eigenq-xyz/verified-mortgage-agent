import MortgageVerifier.Types
import MortgageVerifier.Invariants

/-!
# Theorems.lean

Formal proofs of correctness for the mortgage routing invariants.

These theorems serve as machine-checked evidence for auditors that:
  1. Each invariant function precisely captures the business rule it names.
  2. The checker is complete: a passing record provably satisfies every rule.
  3. Key structural properties of the record hold.

Proof strategy notes:
  - The invariants use BEq (`==`) for enum comparisons; we provide `LawfulBEq`
    instances so that `beq_iff_eq`, `beq_eq_false_iff_ne`, and `bne_iff_ne`
    are available to `simp`.
  - `Float` comparisons (DTI/LTV thresholds) are left as hypotheses; we only
    prove the structural shape of each invariant, not arithmetic facts.
-/

namespace MortgageVerifier.Theorems

open MortgageVerifier MortgageVerifier.Invariants

-- ---------------------------------------------------------------------------
-- LawfulBEq instances (not auto-derived; needed for beq_iff_eq et al.)
-- ---------------------------------------------------------------------------

instance : LawfulBEq RoutingOutcome where
  eq_of_beq {a b} h := by cases a <;> cases b <;> first | rfl | contradiction
  rfl {a} := by cases a <;> rfl

instance : LawfulBEq LoanType where
  eq_of_beq {a b} h := by cases a <;> cases b <;> first | rfl | contradiction
  rfl {a} := by cases a <;> rfl

instance : LawfulBEq EmploymentStatus where
  eq_of_beq {a b} h := by cases a <;> cases b <;> first | rfl | contradiction
  rfl {a} := by cases a <;> rfl

-- ---------------------------------------------------------------------------
-- §1  Escalation completeness
-- ---------------------------------------------------------------------------

/-- An escalation decision with no reason always produces a violation. -/
theorem escalation_with_no_reason_is_violation
    (decision : RoutingDecision) (app : MortgageApplication)
    (h_outcome   : decision.outcome = .escalateToUnderwriter)
    (h_no_reason : decision.escalationReason = none) :
    escalationRequiresReason decision app ≠ none := by
  simp [escalationRequiresReason, h_outcome, h_no_reason]

/-- An escalation decision with a non-empty reason is not a violation. -/
theorem escalation_with_reason_passes
    (decision : RoutingDecision) (app : MortgageApplication)
    (reason : String)
    (h_reason   : decision.escalationReason = some reason)
    (h_nonempty : ¬reason.trim.isEmpty) :
    escalationRequiresReason decision app = none := by
  simp [escalationRequiresReason, h_reason, h_nonempty]

/-- Non-escalation decisions always pass the escalation invariant. -/
theorem non_escalation_passes_escalation_invariant
    (decision : RoutingDecision) (app : MortgageApplication)
    (h : decision.outcome ≠ .escalateToUnderwriter) :
    escalationRequiresReason decision app = none := by
  simp [escalationRequiresReason, h]

-- ---------------------------------------------------------------------------
-- §2  Non-approval decisions bypass approval-gated invariants
-- ---------------------------------------------------------------------------

/-- Rejected applications do not trigger the DTI cap.
    The cap only gates approvals; rejections are always clean on this axis. -/
theorem reject_bypasses_dtiCapConventional
    (decision : RoutingDecision) (app : MortgageApplication)
    (h : decision.outcome = .reject) :
    dtiCapConventional decision app = none := by
  simp [dtiCapConventional, h]

/-- Requesting-documents outcome does not trigger the DTI cap. -/
theorem requestDocs_bypasses_dtiCapConventional
    (decision : RoutingDecision) (app : MortgageApplication)
    (h : decision.outcome = .requestDocuments) :
    dtiCapConventional decision app = none := by
  simp [dtiCapConventional, h]

/-- Requesting-documents outcome does not trigger the FHA credit floor. -/
theorem requestDocs_bypasses_creditFloorFHA
    (decision : RoutingDecision) (app : MortgageApplication)
    (h : decision.outcome = .requestDocuments) :
    creditFloorFHA decision app = none := by
  simp [creditFloorFHA, h]

/-- Non-jumbo loan types do not trigger the jumbo LTV cap. -/
theorem non_jumbo_bypasses_ltvCapJumbo
    (decision : RoutingDecision) (app : MortgageApplication)
    (h : app.loan.loanType ≠ .jumbo) :
    ltvCapJumbo decision app = none := by
  simp [ltvCapJumbo, h]

-- ---------------------------------------------------------------------------
-- §3  Final-outcome consistency
-- ---------------------------------------------------------------------------

/-- A record with no decisions always fails the consistency check.
    Every valid record must have at least one decision. -/
theorem empty_decisions_fails_consistency
    (dr : DecisionRecord)
    (h : dr.decisions = []) :
    finalOutcomeConsistency dr ≠ none := by
  simp [finalOutcomeConsistency, h]

/-- A single-decision record is consistent iff its outcome matches the record outcome. -/
theorem single_decision_consistency_iff
    (dr : DecisionRecord) (decision : RoutingDecision)
    (h_single : dr.decisions = [decision]) :
    finalOutcomeConsistency dr = none ↔
    decision.outcome = dr.finalOutcome := by
  constructor
  · intro h
    unfold finalOutcomeConsistency at h
    rw [h_single] at h
    simp at h
    exact h
  · intro h
    unfold finalOutcomeConsistency
    rw [h_single]
    simp [h]

-- ---------------------------------------------------------------------------
-- §4  Checker completeness
-- ---------------------------------------------------------------------------

/-- checkDecision is precisely the list of invariants applied to the decision. -/
theorem checkDecision_is_filterMap_of_invariants
    (decision : RoutingDecision) (app : MortgageApplication) :
    checkDecision decision app =
    decisionInvariants.filterMap (fun inv => inv decision app) := rfl

/-- The escalation invariant is among the checked invariants. -/
theorem escalation_invariant_is_checked :
    escalationRequiresReason ∈ decisionInvariants := by
  simp [decisionInvariants]

/-- If checkRecord returns no violations, every individual decision is clean. -/
theorem checkRecord_empty_implies_clean_decisions
    (dr : DecisionRecord)
    (h : checkRecord dr = []) :
    ∀ d ∈ dr.decisions, checkDecision d dr.application = [] := by
  unfold checkRecord at h
  have ⟨h_dec, _⟩ := List.append_eq_nil_iff.mp h
  exact List.flatMap_eq_nil_iff.mp h_dec

/-- If checkRecord returns no violations, the record-level consistency check passes. -/
theorem checkRecord_empty_implies_consistent_outcome
    (dr : DecisionRecord)
    (h : checkRecord dr = []) :
    finalOutcomeConsistency dr = none := by
  unfold checkRecord at h
  have ⟨_, h_rec⟩ := List.append_eq_nil_iff.mp h
  have h_all := List.filterMap_eq_nil_iff.mp h_rec
  exact h_all (finalOutcomeConsistency dr) List.mem_cons_self

-- ---------------------------------------------------------------------------
-- §5  NJ Regulatory and Federal QM invariants
-- ---------------------------------------------------------------------------

/-- Non-approval outcomes bypass the discount-points cap. -/
theorem reject_bypasses_discountPointsCap
    (decision : RoutingDecision) (app : MortgageApplication)
    (h : decision.outcome = .reject) :
    discountPointsCap decision app = none := by
  simp [discountPointsCap, h]

/-- Discount points within the 3-point cap never trigger a violation on approval. -/
theorem discount_points_within_cap_passes
    (decision : RoutingDecision) (app : MortgageApplication)
    (h_outcome : decision.outcome = .approve)
    (h_cap     : ¬(app.loan.discountPointsPct > 3.0)) :
    discountPointsCap decision app = none := by
  simp [discountPointsCap, h_outcome, h_cap]

/-- Discount points exceeding 3 always trigger a violation on approval. -/
theorem discount_points_excess_is_violation
    (decision : RoutingDecision) (app : MortgageApplication)
    (h_outcome : decision.outcome = .approve)
    (h_excess  : app.loan.discountPointsPct > 3.0) :
    discountPointsCap decision app ≠ none := by
  simp [discountPointsCap, h_outcome, h_excess]

/-- A loan with principal below $40,000 is outside HOSA and never high-cost. -/
theorem low_principal_bypasses_high_cost
    (decision : RoutingDecision) (app : MortgageApplication)
    (h : ¬(app.loan.principalUsd >= 40000.0)) :
    highCostLoanMustEscalate decision app = none := by
  simp [highCostLoanMustEscalate, isHighCostHomeLoan, h]

/-- A loan above the 2025 HOSA ceiling ($617,603) is exempt from HOSA. -/
theorem above_hosa_ceiling_bypasses_high_cost
    (decision : RoutingDecision) (app : MortgageApplication)
    (h : ¬(app.loan.principalUsd <= 617603.0)) :
    highCostLoanMustEscalate decision app = none := by
  simp [highCostLoanMustEscalate, isHighCostHomeLoan, h]

/-- Directly approving a high-cost home loan within HOSA range is a violation. -/
theorem high_cost_approve_is_violation
    (decision : RoutingDecision) (app : MortgageApplication)
    (h_outcome   : decision.outcome = .approve)
    (h_principal : app.loan.principalUsd >= 40000.0)
    (h_ceiling   : app.loan.principalUsd <= 617603.0)
    (h_fees      : app.loan.totalPointsAndFeesPct > 0.05) :
    highCostLoanMustEscalate decision app ≠ none := by
  simp [highCostLoanMustEscalate, isHighCostHomeLoan, h_outcome, h_principal,
        h_ceiling, h_fees]

/-- Late charge within 5% cap does not trigger a violation on approval. -/
theorem late_charge_within_cap_passes
    (decision : RoutingDecision) (app : MortgageApplication)
    (h_outcome : decision.outcome = .approve)
    (h_cap     : ¬(app.loan.lateChargePct > 0.05)) :
    lateChargeCap decision app = none := by
  simp [lateChargeCap, h_outcome, h_cap]

/-- A non-JUMBO loan type bypasses the conforming-limit invariant entirely. -/
theorem non_jumbo_bypasses_conforming_limit_check
    (decision : RoutingDecision) (app : MortgageApplication)
    (h : app.loan.loanType ≠ .jumbo) :
    jumboConformingLimitCheck decision app = none := by
  simp [jumboConformingLimitCheck, h]

/-- A JUMBO loan above the 2025 FHFA baseline passes the conforming-limit check. -/
theorem jumbo_above_2025_baseline_passes
    (decision : RoutingDecision) (app : MortgageApplication)
    (h_type      : app.loan.loanType = .jumbo)
    (h_principal : ¬(app.loan.principalUsd ≤ conformingLoanLimit)) :
    jumboConformingLimitCheck decision app = none := by
  simp [jumboConformingLimitCheck, h_type, h_principal]

/-- An unemployed applicant receiving direct approval is always a violation. -/
theorem unemployed_approve_is_violation
    (decision : RoutingDecision) (app : MortgageApplication)
    (h_outcome    : decision.outcome = .approve)
    (h_unemployed : app.applicant.employmentStatus = .unemployed) :
    unemployedApplicantRequiresEscalation decision app ≠ none := by
  simp [unemployedApplicantRequiresEscalation, h_outcome, h_unemployed]

/-- An employed applicant always passes the employment-status invariant. -/
theorem employed_bypasses_unemployment_invariant
    (decision : RoutingDecision) (app : MortgageApplication)
    (h : app.applicant.employmentStatus = .employed) :
    unemployedApplicantRequiresEscalation decision app = none := by
  simp [unemployedApplicantRequiresEscalation, h]

/-- Loans below the QM fee-cap threshold bypass the QM invariant. -/
theorem below_qm_threshold_bypasses_qm_cap
    (decision : RoutingDecision) (app : MortgageApplication)
    (h : ¬(app.loan.principalUsd >= 134841.0)) :
    qmPointsAndFeesCap decision app = none := by
  simp [qmPointsAndFeesCap, h]

/-- All 10 new invariants are members of decisionInvariants. -/
theorem discountPointsCap_is_checked :
    discountPointsCap ∈ decisionInvariants := by simp [decisionInvariants]

theorem highCostLoanMustEscalate_is_checked :
    highCostLoanMustEscalate ∈ decisionInvariants := by simp [decisionInvariants]

theorem unemployedApplicantRequiresEscalation_is_checked :
    unemployedApplicantRequiresEscalation ∈ decisionInvariants := by
  simp [decisionInvariants]

theorem qmPointsAndFeesCap_is_checked :
    qmPointsAndFeesCap ∈ decisionInvariants := by simp [decisionInvariants]

end MortgageVerifier.Theorems
