---
area: server
type: fixed
audience: admins
title: Concurrent server actions wait briefly and identify the action still running
---
Startup and shutdown keep their exclusive lock. A competing action waits up to 30 seconds and reports the owner's process and action if it remains busy.
