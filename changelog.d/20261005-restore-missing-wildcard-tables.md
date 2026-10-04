---
area: server
type: fixed
audience: admins
title: Updates restore missing Wildcard character tables without resetting existing data
---
A new corrective update creates only missing Wildcard card and specialization-cache tables. Existing tables and their data are preserved. Release builds now apply SQL on a disposable database before publishing its expected schema.
