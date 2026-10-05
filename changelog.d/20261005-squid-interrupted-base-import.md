---
area: server
type: fixed
audience: admins
title: Interrupted SquidBots database imports require recovery before restarting
---
Base imports record a pending marker before SQL starts and clear it only after SQL and history recording succeed. A later start detects unfinished imports and requests recovery instead of accepting partially filled tables as complete.
