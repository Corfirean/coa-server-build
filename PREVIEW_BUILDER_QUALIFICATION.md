# PREVIEW BUILDER QUALIFICATION REPORT

**Verdict:** PASS
**Qualified:** YES
**Candidate Version:** 0.7.1-preview
**Core Commit:** a11c2a7143c29e4ce8021d63eae319a2cc623f99
**Builder Branch:** preview/modules-v2
**Verification Date:** 2026-11-03 09:04:09
**Failed Checks Count:** 0

## Qualification Matrix

| Check | Status |
|-------|--------|
| CANDIDATE_LOCK_VALID | PASS |
| WORLDSERVER_PRESENT | PASS |
| WORLDSERVER_HASH_MATCH | PASS |
| WORLDSERVER_SIZE_MATCH | PASS |
| SDK_PRESENT | PASS |
| SDK_ABI_MATCH | PASS |
| DUPLICATION_GUARD | PASS |
| OFFICIAL_DYNAMIC_DLLS | PASS |
| OFFICIAL_DLL_HASHES | PASS |
| CHECKSUM_NO_DUPLICATES | PASS |
| CHECKSUM_NO_TRAVERSAL | PASS |
| CHECKSUM_INVENTORY_VALID | PASS |
| CHECKSUM_COVERAGE | PASS |

## Diagnostics & Evidence
- [PASS] CANDIDATE_LOCK_VALID: Candidate lock schema verified successfully (Version: 0.7.1-preview)
- [PASS] WORLDSERVER_PRESENT: worldserver.exe is present in 'C:\games\coa-server-build\dist/server'
- [PASS] WORLDSERVER_HASH_MATCH: worldserver.exe SHA-256 matches lock (048f810e44bcf7e3bcbbc1c6d3037a5f829e6815e959f9f0cf0d3b3c8594fc4b)
- [PASS] WORLDSERVER_SIZE_MATCH: worldserver.exe size matches lock (68840960 bytes)
- [PASS] SDK_PRESENT: sdk.json found and parsed in 'C:\games\coa-server-build\dist/sdk'
- [PASS] SDK_ABI_MATCH: SDK ABI fingerprint matches lock (2f82013def4698d3f75fa24e5f70ffa504a7782d366b5edb78c7adc3c1ee0883)
- [PASS] DUPLICATION_GUARD: Plugin host dynamic symbol export (COA_PLUGIN_HOST) verified
- [PASS] OFFICIAL_DYNAMIC_DLLS: All mandatory official plugins present in 'C:\games\coa-server-build\dist/plugins'
- [PASS] OFFICIAL_DLL_HASHES: All official plugins match candidate lock SHA-256 and metadata
- [PASS] CHECKSUM_NO_DUPLICATES: No duplicate entries in sha256sums.txt
- [PASS] CHECKSUM_NO_TRAVERSAL: Absence of path traversal verified in sha256sums.txt
- [PASS] CHECKSUM_INVENTORY_VALID: All files listed in sha256sums.txt verified successfully
- [PASS] CHECKSUM_COVERAGE: All critical candidate artifacts covered by sha256sums.txt


## Artifact Measurements
- **worldserver.exe SHA-256:** 048f810e44bcf7e3bcbbc1c6d3037a5f829e6815e959f9f0cf0d3b3c8594fc4b
- **worldserver.exe Size:** 68840960 bytes
- **SDK ABI Fingerprint:** 2f82013def4698d3f75fa24e5f70ffa504a7782d366b5edb78c7adc3c1ee0883
