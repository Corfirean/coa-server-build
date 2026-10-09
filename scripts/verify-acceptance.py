"""Bind a passing acceptance result to the exact package being promoted."""
import hashlib
import json
import pathlib
import sys

package = pathlib.Path(sys.argv[1])
manifest = (package / "manifest.json").read_bytes()
report = json.loads((package / "acceptance.json").read_text(encoding="utf-8-sig"))
version = json.loads(manifest)["version"]
if report.get("schema") != 1 or report.get("result") != "passed":
    raise SystemExit("No passing Windows acceptance report")
if report.get("version") != version or report.get("manifestSha256") != hashlib.sha256(manifest).hexdigest():
    raise SystemExit("Acceptance report is for a different package")
if not isinstance(report.get("manager"), str) or len(report["manager"]) != 64:
    raise SystemExit("Acceptance report has no tested manager/tool hash")
if not isinstance(report.get("managerSource"), str) or len(report["managerSource"]) != 40:
    raise SystemExit("Acceptance report has no tested manager source commit")
scenarios = report.get("scenarios", [])
modes = {"coa", "wildcard", "dual", "squid", "imported"}
if {s.get("mode") for s in scenarios if s.get("baseline") == "base"} != modes:
    raise SystemExit("Missing clean/skip-version acceptance for one or more server modes")
if {s.get("mode") for s in scenarios if s.get("baseline") != "base"} != modes:
    raise SystemExit("Missing previous-release acceptance for one or more server modes")
for scenario in scenarios:
    if any(scenario.get(k) != report.get(k) for k in ("result", "version", "manifestSha256", "managerSource")):
        raise SystemExit("A matrix scenario tested different source or package bytes")
    required = {
        "signed-package-corruption", "locked-file", "occupied-port", "python-startup-failure",
        "partial-ddl-invalid-sql", "update-process-crash", "recovery-process-crash",
        "modified-config-preservation", "running-state-recovery", "player-data-preservation",
        "disk-exhaustion", "write-denial", "corrupt-journal", "corrupt-recovery-point",
        "database-process-crash", "new-server-crash", "network-action-containment",
        "all-file-operation-phases",
    }
    missing = required - set(scenario.get("coverage", []))
    if missing:
        raise SystemExit("Required fault coverage is missing: " + ", ".join(sorted(missing)))
print("Acceptance is bound to the exact signed manifest")
