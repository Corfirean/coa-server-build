---
area: server
type: fixed
audience: admins
title: Server releases reject versions older than the current stable package
---
Release builds check the stable package version before publishing and require Manager 0.6.2 or newer for its database update safeguards. Manual releases can specify an explicit version when the build date differs from the release date.
