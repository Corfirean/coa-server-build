---
area: server
type: fixed
audience: admins
title: SquidBots preserves imported bot databases and skips SQL when disabled
---
Existing update histories prevent replay of completed SQL. Imported base tables are adopted without dropping their data; incomplete bases stop with a repair error. Disabled SquidBots performs no SQL provisioning.
