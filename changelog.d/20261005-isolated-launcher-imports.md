---
area: server
type: fixed
audience: admins
title: Server updates no longer fail to start with the bundled Python runtime
---
The launcher and its supervisor can load their integration scripts with the repack's isolated Python runtime. This fixes startup failures after an update.
