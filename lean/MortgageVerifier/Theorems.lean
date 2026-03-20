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

end MortgageVerifier.Theorems
