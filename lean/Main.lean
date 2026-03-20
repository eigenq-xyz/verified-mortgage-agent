import Lean.Data.Json
import MortgageVerifier.Parser
import MortgageVerifier.Checker

/-!
# Main.lean — `lake exe verify-trace` entry point

Usage:
  lake exe verify-trace -- <path-to-record.json>

Exit codes:
  0  all invariants pass
  1  one or more invariant violations
  2  parse error (bad JSON, wrong schema_version, missing fields)

Stdout: JSON object matching Python's `VerificationResult` schema.
Stderr: human-readable diagnostics (not machine-parsed by Python).
-/

open MortgageVerifier

private def EXPECTED_SCHEMA_VERSION : String := "1.0.0"

-- Build a minimal error result JSON for parse failures
private def errorJson (recordId : String) (name : String) (description : String) : String :=
  MortgageVerifier.Checker.resultToJson {
    passed      := false
    recordId    := recordId
    violations  := [{ invariantName := name, description := description, severity := "ERROR" }]
    leanVersion := Lean.versionString
  }

def main (args : List String) : IO UInt32 := do
  -- Validate arguments
  let path ← match args with
    | [p] => pure p
    | _   => do
        IO.eprintln "Usage: verify-trace -- <path-to-record.json>"
        return (2 : UInt32)

  -- Read file
  let content ← try
    IO.FS.readFile path
  catch e =>
    IO.eprintln s!"Error reading file '{path}': {e}"
    return (2 : UInt32)

  -- Parse JSON
  let json ← match Lean.Json.parse content with
    | .error e =>
        IO.eprintln s!"JSON parse error: {e}"
        IO.println (errorJson "unknown" "parse_error" s!"JSON parse error: {e}")
        return (2 : UInt32)
    | .ok j => pure j

  -- Check schema version before full parse
  let version : String :=
    match json with
    | .obj m => (m.get? "schema_version" |>.bind (fun v =>
        match v with | .str s => some s | _ => none)).getD ""
    | _ => ""

  if version != EXPECTED_SCHEMA_VERSION then
    let msg := s!"schema_version '{version}' incompatible with expected '{EXPECTED_SCHEMA_VERSION}'"
    IO.eprintln msg
    IO.println (errorJson "unknown" "schema_version_mismatch" msg)
    return (2 : UInt32)

  -- Parse decision record
  let dr ← match Parser.parseDecisionRecord json with
    | .error e =>
        IO.eprintln s!"Record parse error: {e}"
        IO.println (errorJson "unknown" "parse_error" s!"Record parse error: {e}")
        return (2 : UInt32)
    | .ok t => pure t

  -- Run checker and emit result
  let result := Checker.check dr
  IO.println (Checker.resultToJson result)
  return if result.passed then (0 : UInt32) else (1 : UInt32)
