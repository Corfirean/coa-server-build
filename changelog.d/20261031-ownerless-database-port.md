---
area: server
type: fixed
audience: admins
title: Database restarts recover from ownerless Windows port entries
---
The launcher checks whether a port reported with PID 0 can actually be used and briefly waits for Windows to release it. Ports owned by another process remain protected.
