# P0 Surgical Hardening Report: CoA Modules Preview Release Gates & Artifact Provenance

**Date:** 2026-11-03  
**Repository:** `coa-server-build` (`preview/modules-v2`)  
**Core Reference:** `azerothcore-wotlk-coa` (`preview/dynamic-plugin-host` @ `a11c2a7143c29e4ce8021d63eae319a2cc623f99`)  
**Manager Reference:** `coa-server-manager` (`preview/modules-v2` @ `3dbfffba76c44794a944018f5a1f001cbc80119c`)  
**Builder HEAD:** `a57b2d935a3446d178ac34473124e7df4e512e4c` (with local surgical hardening)

---

## 1. Executive Summary

This engineering session performed surgical P0 hardening on the release qualification gates, artifact provenance, manifest generation, and publication pipelines for the CoA Modules Preview.

All identified defects have been eliminated and verified:
1. **Fail-Closed Qualification:** `preview-verify.ps1` no longer allows silent passes, warnings on hash mismatches, or default zero exit codes. Any defect immediately terminates with `exit 1` and records diagnostics.
2. **Elimination of Synthetic Fallbacks:** `generate-candidate-lock.ps1` now strictly requires live git checkouts, real binaries, real DLLs, and valid semver strings.
3. **Discrepancy Resolution:** The historical documentation divergence regarding `worldserver.exe` size (37,215,744 bytes vs real 68,840,960 bytes) was identified, documented, and bound into `candidate-lock.json` with strict size checking.
4. **Pre-Publish Gate:** `.github/workflows/preview-release.yml` and `scripts/test-publish-gate.ps1` enforce mandatory qualification verdicts, bundle completeness, and cryptographic signatures before publication can proceed.
5. **Manifest Generation Integrity:** Resolved `null` SDK versions in `updates/csm-preview-components.json`, eliminated unversioned download URLs, and cleanly separated Contract 1 (App Updater) from Contract 2 (Component Channel).
6. **20 Negative Tests Passed:** All 20 gate failure modes (GATE-01 to GATE-20) were executed against real fixtures, passing with 100% compliance.

---

## 2. Hardened Architecture & Key Defect Fixes

### P0-A: Fail-Closed Qualification (`scripts/preview-verify.ps1`)
- **Old Behavior:** SHA-256 mismatches printed `WARN` but left the check as `PASS`. Missing files or invalid schemas still returned exit code 0.
- **New Hardened Behavior:**
  - Evaluates 13 explicit checks: `CANDIDATE_LOCK_VALID`, `WORLDSERVER_PRESENT`, `WORLDSERVER_HASH_MATCH`, `WORLDSERVER_SIZE_MATCH`, `SDK_PRESENT`, `SDK_ABI_MATCH`, `DUPLICATION_GUARD`, `OFFICIAL_DYNAMIC_DLLS`, `OFFICIAL_DLL_HASHES`, `CHECKSUM_NO_DUPLICATES`, `CHECKSUM_NO_TRAVERSAL`, `CHECKSUM_INVENTORY_VALID`, `CHECKSUM_COVERAGE`.
  - Emits machine-readable verdict JSON: `preview-qualification-verdict.json` with `"status": "PASS"|"FAIL"` and `"qualified": true|false`.
  - Emits comprehensive markdown diagnostic report: `PREVIEW_BUILDER_QUALIFICATION.md`.
  - Terminates with process `exit 1` on any failure condition.

### P0-B: Elimination of Fabricated Provenance Fallbacks (`scripts/generate-candidate-lock.ps1`)
- **Old Behavior:** Used hardcoded commit hashes and SHA-256 strings if source directories or binaries were missing.
- **New Hardened Behavior:**
  - Queries actual repository HEADs (`git rev-parse HEAD`). Throws fatal terminating error if missing or invalid.
  - Queries actual binary lengths and SHA-256 hashes on disk. Throws fatal terminating error if any required binary or plugin is absent.
  - Records both byte `size` and SHA-256 `sha256` in candidate lock.

### P0-C: Binary Size vs Hash Discrepancy Resolution
- **Actual Binary on Disk:**
  - File: `dist/server/worldserver.exe`
  - Byte Size: `68,840,960` bytes
  - SHA-256: `048f810e44bcf7e3bcbbc1c6d3037a5f829e6815e959f9f0cf0d3b3c8594fc4b`
- **Root Cause:** Historical documentation referenced an early unlinked intermediate build size (37,215,744 bytes).
- **Resolution:** Updated `candidate-lock.json` with `size: 68840960`. Added GATE-15 regression test verifying that conflicting size metadata on matching SHA-256 triggers a fatal qualification error.

### P0-D: Pre-Publish Gate Enforcement (`scripts/test-publish-gate.ps1` & Workflows)
- Added dedicated `scripts/test-publish-gate.ps1`.
- Integrated directly into `.github/workflows/preview-release.yml` before `gh release create`.
- Checks:
  1. `preview-qualification-verdict.json` exists and has `status == "PASS"` and `qualified == true`.
  2. All required release assets exist in bundle and are non-empty.
  3. App updater manifest has a non-empty, valid cryptographic minisign signature.
  4. Component manifest has non-null SDK version and valid download URLs.

### P0-E: Manifest Contracts Separation & Null SDK Resolution
- In `generate-candidate-lock.ps1` and `preview-package.ps1`:
  - Fixed variable assignment where missing `.version` in `sdk.json` caused `$sdkVersion` to be overwritten with `$null`.
  - Resolved valid semver version `"0.3.2"`.
  - Contract 2 component manifest now properly references `coa-plugin-sdk-v0.3.2.zip` and sets `required_sdk: "0.3.2"` for all official modules.
  - Normalized all `sha256sums.txt` entries to use portable forward slashes `/`.

---

## 3. Negative Test Suite Results (GATE-01 to GATE-20)

| Test ID | Scenario | Expected | Actual | Verdict |
|---------|----------|----------|--------|---------|
| **GATE-01** | Valid candidate bundle | Exit 0, PASS | Exit 0, PASS | **PASS** |
| **GATE-02** | Missing `worldserver.exe` | Exit 1, FAIL | Exit 1, FAIL | **PASS** |
| **GATE-03** | Corrupted / modified `worldserver.exe` | Exit 1, FAIL | Exit 1, FAIL | **PASS** |
| **GATE-04** | Incorrect host SHA-256 in candidate lock | Exit 1, FAIL | Exit 1, FAIL | **PASS** |
| **GATE-05** | Missing SDK manifest (`sdk.json`) | Exit 1, FAIL | Exit 1, FAIL | **PASS** |
| **GATE-06** | SDK ABI fingerprint mismatch | Exit 1, FAIL | Exit 1, FAIL | **PASS** |
| **GATE-07** | Missing required official DLL (`companions.dll`) | Exit 1, FAIL | Exit 1, FAIL | **PASS** |
| **GATE-08** | Corrupted required official DLL | Exit 1, FAIL | Exit 1, FAIL | **PASS** |
| **GATE-09** | DLL SHA-256 mismatch against candidate lock | Exit 1, FAIL | Exit 1, FAIL | **PASS** |
| **GATE-10** | Malformed candidate lock JSON | Exit 1, FAIL | Exit 1, FAIL | **PASS** |
| **GATE-11** | Missing required source commit in lock | Exit 1, FAIL | Exit 1, FAIL | **PASS** |
| **GATE-12** | Duplicate checksum entry in `sha256sums.txt` | Exit 1, FAIL | Exit 1, FAIL | **PASS** |
| **GATE-13** | Missing checksum entry for bundle file | Exit 1, FAIL | Exit 1, FAIL | **PASS** |
| **GATE-14** | Path traversal (`..`) in `sha256sums.txt` | Exit 1, FAIL | Exit 1, FAIL | **PASS** |
| **GATE-15** | Same hash / conflicting size metadata | Exit 1, FAIL | Exit 1, FAIL | **PASS** |
| **GATE-16** | Missing Manager signature in updater manifest | Exit 1, Publish Blocked | Exit 1, Publish Blocked | **PASS** |
| **GATE-17** | Malformed / invalid updater signature | Exit 1, Publish Blocked | Exit 1, Publish Blocked | **PASS** |
| **GATE-18** | Invalid component SDK version (null/empty) | Exit 1, Publish Blocked | Exit 1, Publish Blocked | **PASS** |
| **GATE-19** | Missing release asset in bundle | Exit 1, Publish Blocked | Exit 1, Publish Blocked | **PASS** |
| **GATE-20** | Unqualified candidate (verdict FAIL) | Exit 1, Publish Blocked | Exit 1, Publish Blocked | **PASS** |

**Summary:** 20 total tests, 20 passed, 0 failed.

---

## 4. Evidence Deliverables Index

- `report/preview-release-gates/negative-test-results.json`: Full machine-readable execution results of all 20 tests.
- `report/preview-release-gates/candidate-integrity.json`: Complete resolution of size/hash consistency, physical measurements, and compiler metadata.
- `report/preview-release-gates/manifest-validation.json`: Detailed validation of Contract 1 (Tauri app) and Contract 2 (Components).
- `report/preview-release-gates/ci-execution-evidence.json`: Analysis of GitHub Actions workflow scoping and local CI parity verification.
- `report/preview-release-gates/publication-gate.json`: Pre-publish checklist and unblock requirements for the owner.
