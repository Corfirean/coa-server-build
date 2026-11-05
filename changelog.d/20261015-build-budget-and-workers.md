---
area: server
type: fixed
audience: admins
title: Server compilation uses available workers and reserves time to save its cache
---
Windows compilation uses up to four workers on machines with at least 12 GB of memory. Its 270-minute budget leaves time within the 330-minute job limit to stop compilation, flush the compiler cache and upload diagnostics, including when compilation does not finish.
