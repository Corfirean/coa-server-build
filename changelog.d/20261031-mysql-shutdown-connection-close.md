---
area: server
type: fixed
audience: admins
title: Database shutdown succeeds when MySQL closes its connection before replying
---
The launcher verifies that its recorded database process has exited before accepting a shutdown connection error. A failed shutdown still reports an error if that process remains running.
