---
area: server
type: fixed
audience: admins
title: Stop an unfinished server startup before restoring its database
---
The launcher can stop its own world process when the console is unavailable. Database shutdown and recovery still wait until that process has stopped.
