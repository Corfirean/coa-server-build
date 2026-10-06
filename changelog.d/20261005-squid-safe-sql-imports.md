---
area: server
type: fixed
audience: admins
title: SquidBots preserves imported bot databases and skips SQL when disabled
---
Imported installer and update histories prevent SQL replay. Each base file preserves complete existing tables, creates entirely missing tables, and stops on partial structure. Existing bot data without history requires repair. Disabled SquidBots skips SQL.
