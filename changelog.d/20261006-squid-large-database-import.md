---
area: server
type: fixed
audience: admins
title: Large SQUID database imports no longer use the short query timeout
---
Initial imports larger than one megabyte receive up to fifteen minutes to finish. Normal database queries keep their existing deadline, and interrupted imports remain blocked until recovered.
