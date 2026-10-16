# Direct server upgrades

New candidates include every available published signed server source, including the base and the currently retained legacy stable/edge packages. Sources are frozen before packaging by manifest and signature digests. Paginated release discovery does not discard old versions after a fixed number of releases. Different signed manifests claiming one source version require investigation and block packaging.

The compatibility matrix contains all frozen versions and their signed schema contracts. The release job qualifies each source directly against the candidate using the production Manager updater. Every result binds the source manifest digest, source schema digest and target version. Missing, failed or skipped old-source checks block publication and stable promotion. Existing packages retain their original signed compatibility policy; this change does not rewrite released manifests.

Only one historical archive is downloaded at a time. Its signature, archive hashes and sizes are verified before use. The job retains all manifests and qualification reports, releases successful disposable fixtures and removes the old archive before testing the next source. Server binaries are compiled once, or reused under the existing exact-source SQL-only checks.

The Manager uses database history to skip applied SQL. Version support does not mean that every manually modified or partially migrated database is known. Unknown imported repacks need a separate state reconciliation; assigning an official version or marking all SQL applied is not an import procedure. Deleted historical releases cannot be reconstructed from a version string and must be recovered as signed source fixtures before claiming coverage.

Expanded source coverage requires Manager 0.6.20 or newer for shared account history and durable legacy history. Publish that Manager before promoting the next server package. Do not call the expanded routes qualified until their individual full-upgrade reports pass.
