# Direct server upgrades

Manager 0.6.21 selects the latest signed package for any known older version. Database history decides which SQL to run. The signed source-version list records test coverage and does not prohibit unlisted versions. Unknown imported versions and downgrades remain blocked. Existing signed server packages do not need rewriting.

Release packaging freezes every available published signed source in historicalUpgradeSources, including retained legacy stable/edge packages, and runs the base plus two recent representative direct upgrades from upgradeSources. Their reports and signed schema contracts remain mandatory publication checks. The complete historical set is not run sequentially inside the packaging job.

Run direct-upgrade-tests.yml against an already published signed candidate or stable version for complete historical acceptance. It freezes the exact Manager revision and source manifests, builds the native verifier/updater once, and runs independent Windows fixtures in parallel. Each source has its own logs, timeout and report. An aggregate check rejects missing, failed or mismatched reports. This workflow neither compiles C++ nor publishes a server. The release and historical test lists describe only the checks actually executed; neither is a promise about every manually altered database.

The Manager uses database history to skip applied SQL. Version support does not mean that every manually modified or partially migrated database is known. Unknown imported repacks need a separate state reconciliation; assigning an official version or marking all SQL applied is not an import procedure. Deleted historical releases cannot be reconstructed from a version string and must be recovered as signed source fixtures before claiming coverage.

New server packages require Manager 0.6.21 or newer, including shared account history and durable legacy history. Do not call historical routes qualified until their individual full-upgrade reports pass. Do not weaken migration guards, infer applied SQL from version numbers, or replace target schema/startup validation with version membership.
