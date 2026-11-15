---
area: server
type: fixed
audience: admins
title: Stopping the server no longer leaves the world running now and then
---
The launcher reads the world console's reply to its shutdown request before disconnecting. Disconnecting at once could lose the request, and the stop then timed out with the world still running.
